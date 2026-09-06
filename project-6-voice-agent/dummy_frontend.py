import streamlit as st

import datetime as dt

import requests

st.title("Appointment Scheduler")

base_url = st.text_input("Base URL", value="https://a0a3-2600-1700-5c50-1bb0-4d-4810-3443-f8fc.ngrok-free.app")

patient_name = st.text_input("Patient Name")
reason = st.text_input("Reason")
start_date = st.date_input("Start Date")
start_time = st.time_input("Start Time")
start_datetime = dt.datetime.combine(start_date, start_time)

if st.button("Schedule Appointment"):
    response = requests.post(f"{base_url}/schedule_appointment/", json={
        "patient_name": patient_name,
        "reason": reason,
        "start_time": start_datetime.isoformat()
    })
    st.write(response.json())

appointments_date = st.date_input("Appointment Date", key="check_appointments_date", value=dt.date.today())
if st.button("List Appointments"):
    response = requests.post(f"{base_url}/list_appointments/", json={
        "date": appointments_date.isoformat()
    })
    st.write(response.json())

patient_name_cancel = st.text_input("Patient Name to Cancel")
cancel_date = st.date_input("Cancel Date", key="check_cancel_date", value=dt.date.today())
cancel_time = st.time_input("Cancel Time", key="check_cancel_time")

start_datetime_cancel = dt.datetime.combine(cancel_date, cancel_time)
if st.button("Cancel Appointment"):
    response = requests.post(f"{base_url}/cancel_appointment/", json={
        "patient_name": patient_name_cancel,
        "start_time": start_datetime_cancel.isoformat()
    })
    st.write(response.json())