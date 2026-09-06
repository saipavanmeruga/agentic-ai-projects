from datetime import datetime

from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
SQLALCHEMY_DATABASE_URL = "sqlite:///appointments_db.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

Base = declarative_base()

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, index=True)
    patient_name = Column(String, index=True)
    reason = Column(String, index=True)
    cancelled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Appointment {self.id}>"

def init_db():
    Base.metadata.create_all(bind=engine)
def get_db():
    db: Session = Session(engine)
    try:
        yield db
    finally:
        db.close()

init_db()

print("Database initialized successfully")