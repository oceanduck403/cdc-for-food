from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.security import get_current_subject
from app.models.user import User
from app.models.chat import ConsultAssignment
from app.models.appointment import Appointment, DoctorPresence
from app.services.appointment_service import book, serialize, match_waiting, online_doctors, lock_patient, assign

router = APIRouter()


async def require(db, sub, role):
    try:
        user = await db.get(User, int(sub))
    except (TypeError, ValueError):
        raise HTTPException(401, '请重新登录')
    if not user or not user.is_active:
        raise HTTPException(401, '账号不可用，请重新登录')
    if user.role != role:
        raise HTTPException(403, '无权执行此操作')
    return user


@router.post('/mine')
async def create(sub=Depends(get_current_subject), db: AsyncSession = Depends(get_db)):
    user = await require(db, sub, 'patient')
    return await serialize(db, await book(db, user.id))


@router.get('/mine')
async def mine(sub=Depends(get_current_subject), db: AsyncSession = Depends(get_db)):
    user = await require(db, sub, 'patient')
    appointment = (await db.execute(select(Appointment).where(Appointment.patient_id == user.id))).scalar_one_or_none()
    return await serialize(db, appointment)


@router.delete('/mine')
async def cancel(sub=Depends(get_current_subject), db: AsyncSession = Depends(get_db)):
    user = await require(db, sub, 'patient')
    await lock_patient(db, user.id)
    appointment = (await db.execute(select(Appointment).where(Appointment.patient_id == user.id))).scalar_one_or_none()
    if not appointment or appointment.status != 'waiting':
        raise HTTPException(409, '预约状态已变化，请刷新后重试')
    appointment.status = 'cancelled'
    await db.commit()
    return await serialize(db, appointment)


@router.post('/heartbeat')
async def heartbeat(sub=Depends(get_current_subject), db: AsyncSession = Depends(get_db)):
    user = await require(db, sub, 'doctor')
    await lock_patient(db, user.id)
    presence = await db.get(DoctorPresence, user.id)
    if presence is None:
        db.add(DoctorPresence(doctor_id=user.id, last_seen=datetime.utcnow()))
    else:
        presence.last_seen = datetime.utcnow()
    await db.commit()
    await match_waiting(db)
    return {'available': user.is_available, 'online': True}


@router.get('/dispatch')
async def dispatch(sub=Depends(get_current_subject), db: AsyncSession = Depends(get_db)):
    await require(db, sub, 'admin')
    online = {d.id for d in await online_doctors(db)}
    doctors = (await db.execute(select(User).where(User.role == 'doctor', User.is_active.is_(True)).order_by(User.id))).scalars().all()
    rows = (await db.execute(select(Appointment, User).join(User, User.id == Appointment.patient_id).where(
        Appointment.status.in_(['waiting', 'assigned'])
    ).order_by(Appointment.created_at, Appointment.id))).all()
    result = []
    for appointment, patient in rows:
        result.append({**await serialize(db, appointment), 'patient_name': patient.real_name or patient.nickname or f'患者{patient.id}'})
    return {'appointments': result, 'doctors': [{'id': d.id, 'name': d.real_name or d.nickname or f'医生{d.id}',
            'online': d.id in online, 'available': d.is_available} for d in doctors]}


class DispatchRequest(BaseModel):
    action: str
    doctor_id: int | None = None


@router.post('/dispatch/{appointment_id}')
async def adjust(appointment_id: int, body: DispatchRequest, sub=Depends(get_current_subject), db: AsyncSession = Depends(get_db)):
    await require(db, sub, 'admin')
    appointment = await db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(404, '预约不存在')
    await lock_patient(db, appointment.patient_id)
    await db.refresh(appointment)
    if appointment.status not in ('waiting', 'assigned'):
        raise HTTPException(409, '预约已结束，请刷新列表')
    if body.action == 'assign':
        if body.doctor_id is None:
            raise HTTPException(422, '请选择医生')
        await assign(db, appointment, body.doctor_id)
    elif body.action in ('complete', 'queue'):
        await db.execute(update(ConsultAssignment).where(ConsultAssignment.patient_id == appointment.patient_id,
            ConsultAssignment.status == 'active').values(status='closed'))
        appointment.status = 'completed' if body.action == 'complete' else 'waiting'
        appointment.assignment_id = None
    else:
        raise HTTPException(422, '未知调度操作')
    await db.commit()
    return await serialize(db, appointment)


class AvailabilityRequest(BaseModel):
    available: bool


@router.put('/doctors/{doctor_id}')
async def availability(doctor_id: int, body: AvailabilityRequest, sub=Depends(get_current_subject), db: AsyncSession = Depends(get_db)):
    await require(db, sub, 'admin')
    doctor = await db.get(User, doctor_id)
    if not doctor or doctor.role != 'doctor' or not doctor.is_active:
        raise HTTPException(404, '医生不存在')
    doctor.is_available = body.available
    await db.commit()
    if body.available:
        await match_waiting(db)
    return {'available': doctor.is_available}
