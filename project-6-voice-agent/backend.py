#Step 1: Import necessary libraries
#Import Database Objects
from re import A

from numpy import str_
from sqlalchemy.engine.result import Result
from database_init import init_db, get_db, Appointment
from sqlalchemy.orm import Session

init_db()
#Step 3: Create Database Contracts
import datetime as dt
from pydantic import BaseModel

class AppointmentRequest(BaseModel):
    patient_name: str
    reason: str
    start_time: dt.datetime


class AppointmentResponse(BaseModel):
    id: int
    patient_name: str
    reason: str | None
    start_time: dt.datetime
    cancelled: bool
    created_at: dt.datetime
    updated_at: dt.datetime
class ListAppointmentsRequest(BaseModel):
    date: str
class ListAppointmentsResponse(BaseModel):
    appointments: list[AppointmentResponse]

class CancelAppointmentRequest(BaseModel):
    patient_name: str
    start_time: dt.datetime


class CancelAppointmentResponse(BaseModel):
    cancelled_count: int

#Step 2: Create a FastAPI instance and endpoints pseudo code

from fastapi import FastAPI, HTTPException, Depends
app = FastAPI()
#schedule appointment endpoint
@app.post("/schedule_appointment/")
def schedule_appointment(request: AppointmentRequest, db: Session = Depends(get_db)):
    #logic to schedule an appointment, write row to database
    new_appointment = Appointment(
        patient_name=request.patient_name,
        reason=request.reason,
        start_time=request.start_time,
        cancelled=False,
        created_at=dt.datetime.now(),
        updated_at=dt.datetime.now()
    )
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)
    new_appointment_response = AppointmentResponse(
        id = new_appointment.id,
        patient_name = new_appointment.patient_name,
        reason = new_appointment.reason,
        start_time = new_appointment.start_time,
        cancelled = new_appointment.cancelled,
        created_at = new_appointment.created_at,
        updated_at = new_appointment.updated_at
    )
    return new_appointment_response

from sqlalchemy import select
@app.post("/cancel_appointment/")
def cancel_appointment(request: CancelAppointmentRequest, db: Session = Depends(get_db)):
    start_dt  = dt.datetime.combine(request.start_time, dt.time.min)
    end_dt = start_dt + dt.timedelta(days=1)
    result = db.execute(
        select(Appointment)
        .where(Appointment.patient_name == request.patient_name)
        .where(Appointment.start_time >= start_dt)  
        .where(Appointment.start_time <= end_dt)
        .where(Appointment.cancelled == False)
    )
    appointments = result.scalars().all()
    if len(appointments) == 0:
        raise HTTPException(status_code=404, detail="No appointment found for the given patient and start time")
    for appointment in appointments:
        appointment.cancelled = True
        appointment.updated_at = dt.datetime.now()
    db.commit()
    return CancelAppointmentResponse(cancelled_count=len(appointments))
    #logic to cancel an appointment, update row in database

@app.post("/list_appointments/")
def list_appointments(request: ListAppointmentsRequest, db: Session = (Depends(get_db))):
    #logic to list all appointments, read rows from database
    print(request.date)
    start_dt  = dt.datetime.strptime(request.date, "%Y-%m-%d").date()
    end_dt = start_dt + dt.timedelta(days=1)
    result = db.execute(
        select(Appointment)
        .where(Appointment.start_time.between(start_dt, end_dt))    
        .where(Appointment.cancelled == False)
        .order_by(Appointment.start_time.asc())
    )
    appointments = result.scalars().all()
    booked_appointments = []
    for appointment in appointments:
        # print(appointment)
        appointment_obj = (AppointmentResponse(
            id=appointment.id,
            patient_name=appointment.patient_name,
            reason=appointment.reason,
            start_time=appointment.start_time,
            cancelled=appointment.cancelled,
            created_at=appointment.created_at,
            updated_at=appointment.updated_at
        ))
        booked_appointments.append(appointment_obj)
    return booked_appointments


#step 4: Create Business Logic
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)

#step 5: streamlit dashboard
