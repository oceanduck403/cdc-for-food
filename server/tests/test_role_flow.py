import pytest
from app.models.user import User
from app.core.security import hash_password, create_access_token
pytestmark = pytest.mark.asyncio
async def test_role_login_and_complete_consultation(client, db):
    doctor=User(role='doctor',username='flow_doctor',password_hash=hash_password('Flow-test-123'),real_name='Test doctor')
    admin=User(role='admin',username='flow_admin',password_hash=hash_password('Flow-test-123'))
    patient=User(role='patient',nickname='Test patient')
    db.add_all([doctor,admin,patient]);await db.commit()
    async def login(user,password='Flow-test-123',role=None):
        return await client.post('/api/v1/auth/account-login',json={'username':user.username,'password':password,'role':role or user.role})
    dh={};ah={}
    for user,h in [(doctor,dh),(admin,ah)]:
        response=await login(user);assert response.status_code==200,response.text
        assert response.json()['profile']['id']==user.id
        h['Authorization']='Bearer '+response.json()['token']
    ph={'Authorization':'Bearer '+create_access_token(str(patient.id))}
    for path in ['/admin/stats','/admin/doctors','/admin/patients','/admin/assignments','/admin/chats','/appointments/dispatch']:
        response=await client.get('/api/v1'+path,headers=ah);assert response.status_code==200,(path,response.text)
        assert (await client.get('/api/v1'+path,headers=ph)).status_code==403
    assert (await login(doctor,'wrong')).status_code==401
    assert (await login(doctor,role='admin')).status_code in (403,404)
    assert (await client.post('/api/v1/appointments/heartbeat',headers=dh)).status_code==200
    booking=await client.post('/api/v1/appointments/mine',headers=ph);assert booking.status_code==200,booking.text
    assigned=await client.post('/api/v1/appointments/dispatch/'+str(booking.json()['id']),headers=ah,json={'action':'assign','doctor_id':doctor.id})
    assert assigned.status_code==200,assigned.text
    aid=assigned.json()['assignment_id']
    patients=await client.get('/api/v1/chat/doctor/patients',headers=dh)
    assert patients.status_code==200,patients.text
    assert any(p['patient_id']==patient.id for p in patients.json()['patients'])
    detail=await client.get('/api/v1/chat/doctor/patient-detail/'+str(patient.id),headers=dh);assert detail.status_code==200,detail.text
    for h,content in [(ph,'Test question'),(dh,'Test reply')]:
        response=await client.post('/api/v1/chat/send',headers=h,json={'assignment_id':aid,'content':content});assert response.status_code==200,response.text
    messages=await client.get('/api/v1/chat/messages',headers=ph,params={'assignment_id':aid})
    assert messages.status_code==200,messages.text
    assert [m['content'] for m in messages.json()['messages']]==['Test question','Test reply']
    assert (await client.post('/api/v1/chat/read',headers=dh,params={'assignment_id':aid})).status_code==200
    doctor.is_active=False;await db.commit()
    assert (await login(doctor)).status_code==403
