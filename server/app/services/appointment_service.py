from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select, update, func
from app.models.user import User
from app.models.chat import ConsultAssignment
from app.models.appointment import Appointment, DoctorPresence

ONLINE_SECONDS = 90


async def lock_patient(db, patient_id):
    # UPDATE obtains a write lock on SQLite and a row lock on PostgreSQL.
    # It serializes repeated booking/dispatch requests for the same patient.
    await db.execute(update(User).where(User.id == patient_id).values(is_active=User.is_active))


async def online_doctors(db):
    cutoff = datetime.utcnow() - timedelta(seconds=ONLINE_SECONDS)
    return (await db.execute(select(User).join(DoctorPresence, DoctorPresence.doctor_id == User.id).where(
        User.role == 'doctor', User.is_active.is_(True), User.is_available.is_(True), DoctorPresence.last_seen >= cutoff
    ).order_by(User.id))).scalars().all()


async def assign(db, appointment, doctor_id=None):
    doctors = await online_doctors(db)
    if doctor_id is not None:
        doctors = [d for d in doctors if d.id == doctor_id]
        if not doctors:
            raise HTTPException(409, '该医生离线或已暂停接诊，请刷新后选择')
    if not doctors:
        return
    counts = dict((await db.execute(select(ConsultAssignment.doctor_id, func.count()).where(
        ConsultAssignment.status == 'active'
    ).group_by(ConsultAssignment.doctor_id))).all())
    chosen = min(doctors, key=lambda d: (counts.get(d.id, 0), d.id))
    # Close, rather than overwrite, old sessions so historical records stay intact.
    await db.execute(update(ConsultAssignment).where(
        ConsultAssignment.patient_id == appointment.patient_id, ConsultAssignment.status == 'active'
    ).values(status='closed'))
    session = ConsultAssignment(patient_id=appointment.patient_id, doctor_id=chosen.id, status='active')
    db.add(session)
    await db.flush()
    appointment.assignment_id = session.id
    appointment.status = 'assigned'


async def book(db, patient_id):
    await lock_patient(db, patient_id)
    appointment = (await db.execute(select(Appointment).where(Appointment.patient_id == patient_id))).scalar_one_or_none()
    if appointment is None:
        appointment = Appointment(patient_id=patient_id, status='waiting')
        db.add(appointment)
        # Preserve an existing active consultation when adopting older accounts.
        existing = (await db.execute(select(ConsultAssignment).where(
            ConsultAssignment.patient_id == patient_id, ConsultAssignment.status == 'active'
        ).order_by(ConsultAssignment.id.desc()))).scalars().first()
        if existing:
            appointment.assignment_id, appointment.status = existing.id, 'assigned'
    elif appointment.status in ('cancelled', 'completed'):
        appointment.status, appointment.assignment_id = 'waiting', None
        appointment.created_at = datetime.utcnow()
    if appointment.status == 'waiting':
        await assign(db, appointment)
    await db.commit()
    return appointment


async def match_waiting(db):
    ids = (await db.execute(select(Appointment.patient_id).where(Appointment.status == 'waiting').order_by(Appointment.created_at, Appointment.id))).scalars().all()
    for patient_id in ids:
        await book(db, patient_id)


async def serialize(db, appointment):
    if appointment is None:
        return {'status': 'none', 'fee': 0, 'doctor': None, 'assignment_id': None}
    session = await db.get(ConsultAssignment, appointment.assignment_id) if appointment.assignment_id else None
    doctor = await db.get(User, session.doctor_id) if session else None
    online = {d.id for d in await online_doctors(db)}
    return {
        'id': appointment.id, 'patient_id': appointment.patient_id, 'status': appointment.status, 'fee': 0,
        'assignment_id': session.id if session and session.status == 'active' else None,
        'created_at': appointment.created_at.isoformat() if appointment.created_at else None,
        'doctor': {'id': doctor.id, 'name': doctor.real_name or doctor.nickname or '医生', 'title': doctor.title,
                   'department': doctor.department, 'intro': doctor.intro, 'online': doctor.id in online} if doctor else None,
    }
