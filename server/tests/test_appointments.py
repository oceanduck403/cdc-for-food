from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from app.core.security import admin_auth_fingerprint, create_access_token, hash_password
from app.models.user import User
from app.models.appointment import DoctorPresence, Appointment
from app.models.chat import ConsultAssignment

pytestmark = pytest.mark.asyncio

def headers(user):
    extra = {'role': user.role}
    if user.role == 'admin':
        extra['admin_auth'] = admin_auth_fingerprint(user)
    return {'Authorization': 'Bearer ' + create_access_token(str(user.id), extra=extra)}

async def test_free_booking_queue_online_dispatch_and_permissions(client, db):
    patient = User(role='patient', nickname='预约测试')
    outsider = User(role='patient', nickname='其他患者')
    doctor = User(role='doctor', nickname='医生甲', is_available=True)
    second = User(role='doctor', nickname='医生乙', is_available=True)
    admin = User(role='admin', nickname='调度员', username='appointment_admin', password_hash=hash_password('Admin-test-123'))
    db.add_all([patient, outsider, doctor, second, admin]); await db.commit()
    base = '/api/v1/appointments'
    assert (await client.post(base + '/mine')).status_code == 401
    assert (await client.get(base + '/dispatch', headers=headers(patient))).status_code == 403
    assert (await client.post(base + '/heartbeat', headers=headers(patient))).status_code == 403
    response = await client.post(base + '/mine', headers=headers(patient))
    assert response.status_code == 200, response.text
    booking = response.json()
    assert booking['status'] == 'waiting' and booking['fee'] == 0
    assert (await client.post(base + '/mine', headers=headers(patient))).json()['id'] == booking['id']
    assert (await client.get(base + '/mine', headers=headers(outsider))).json()['status'] == 'none'
    # Merely having is_available=True is not proof of being online.
    assert (await client.get(base + '/dispatch', headers=headers(admin))).json()['doctors'][-1]['online'] is False
    assert (await client.post(base + '/heartbeat', headers=headers(doctor))).status_code == 200
    matched = (await client.get(base + '/mine', headers=headers(patient))).json()
    assert matched['status'] == 'assigned' and matched['doctor']['id'] == doctor.id
    old_session = matched['assignment_id']
    assert (await client.delete(base + '/mine', headers=headers(patient))).status_code == 409
    assert (await client.post(base + '/mine', headers=headers(patient))).json()['assignment_id'] == old_session
    assert (await client.post(base + f'/dispatch/{booking["id"]}', headers=headers(admin), json={'action': 'assign', 'doctor_id': second.id})).status_code == 409
    await client.post(base + '/heartbeat', headers=headers(second))
    moved = await client.post(base + f'/dispatch/{booking["id"]}', headers=headers(admin), json={'action': 'assign', 'doctor_id': second.id})
    assert moved.status_code == 200, moved.text
    assert moved.json()['doctor']['id'] == second.id
    assert moved.json()['assignment_id'] != old_session
    closed = await db.get(ConsultAssignment, old_session)
    assert closed.status == 'closed'
    stale_send = await client.post('/api/v1/chat/send', headers=headers(patient), json={'assignment_id': old_session, 'content': '已改派'})
    assert stale_send.status_code == 409
    await client.put(base + f'/doctors/{second.id}', headers=headers(admin), json={'available': False})
    await client.post(base + '/heartbeat', headers=headers(second))
    status = (await client.get(base + '/dispatch', headers=headers(admin))).json()
    assert next(d for d in status['doctors'] if d['id'] == second.id)['available'] is False
    await client.post(base + f'/dispatch/{booking["id"]}', headers=headers(admin), json={'action': 'complete'})
    assert (await client.get(base + '/mine', headers=headers(patient))).json()['status'] == 'completed'
    assert (await client.post(base + f'/dispatch/{booking["id"]}', headers=headers(admin), json={'action': 'queue'})).status_code == 409
    # Expired heartbeats must not receive new bookings.
    presence = await db.get(DoctorPresence, doctor.id)
    presence.last_seen = datetime.utcnow() - timedelta(minutes=3)
    await db.commit()
    waiting = (await client.post(base + '/mine', headers=headers(patient))).json()
    assert waiting['status'] == 'waiting'
    assert (await client.delete(base + '/mine', headers=headers(patient))).json()['status'] == 'cancelled'
    rows = (await db.execute(select(Appointment).where(Appointment.patient_id == patient.id))).scalars().all()
    assert len(rows) == 1


async def test_concurrent_booking_and_least_loaded_online_doctor(tmp_path):
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.models.base import Base
    from app.services.appointment_service import book
    engine = create_async_engine('sqlite+aiosqlite:///' + str(tmp_path / 'appointments.db'))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        patients = [User(role='patient') for _ in range(3)]
        doctors = [User(role='doctor', is_available=True) for _ in range(2)]
        db.add_all(patients + doctors); await db.commit()
        for doctor in doctors:
            db.add(DoctorPresence(doctor_id=doctor.id, last_seen=datetime.utcnow()))
        await db.commit()
    async def reserve(patient_id):
        async with sessions() as db:
            appointment = await book(db, patient_id)
            return appointment.id, appointment.assignment_id
    try:
        results = await asyncio.gather(*(reserve(patients[0].id) for _ in range(5)))
        assert len(set(results)) == 1
        await reserve(patients[1].id)
        async with sessions() as db:
            assignments = (await db.execute(select(ConsultAssignment).where(ConsultAssignment.status == 'active'))).scalars().all()
            assert len(assignments) == 2
            assert {a.doctor_id for a in assignments} == {d.id for d in doctors}
    finally:
        await engine.dispose()
