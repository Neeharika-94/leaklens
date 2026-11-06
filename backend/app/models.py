import os
from datetime import datetime, timezone
from sqlalchemy import (JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint, create_engine)
from sqlalchemy.orm import declarative_base, sessionmaker
engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./leaklens.db"), future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()
now = lambda: datetime.now(timezone.utc)
M = lambda: Numeric(14, 2)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True); email = Column(String, unique=True, index=True)
    name = Column(String); firm = Column(String); pw_hash = Column(String)
    role = Column(String, default="accountant")  # super_admin | accountant | founder
    active = Column(Boolean, default=True); currency = Column(String, default="INR"); created = Column(DateTime, default=now)
class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True); accountant_id = Column(ForeignKey("users.id"), index=True)
    company = Column(String); slug = Column(String); industry = Column(String); contact = Column(String)
    email = Column(String); currency = Column(String, default="INR"); archived = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("accountant_id", "slug"),)
class Audit(Base):
    __tablename__ = "audits"
    id = Column(Integer, primary_key=True); code = Column(String, unique=True, index=True)
    customer_id = Column(ForeignKey("customers.id"), index=True); accountant_id = Column(ForeignKey("users.id"), index=True)
    title = Column(String); period = Column(String); status = Column(String, default="Draft"); created = Column(DateTime, default=now)
class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True); audit_id = Column(ForeignKey("audits.id"), index=True)
    fingerprint = Column(String); category = Column(String); merchant = Column(String)
    currency = Column(String); frequency = Column(String); description = Column(Text)
    evidence = Column(JSON, default=list); confidence = Column(String)
    original = Column(JSON)                       # immutable copy of what Claude submitted
    recommendation = Column(Text)                 # original Claude recommendation
    approved_recommendation = Column(Text)        # accountant correction, stored separately
    calc_inputs = Column(JSON, default=dict); calc_result = Column(JSON)
    annual_expense = Column(M(), default=0); potential = Column(M(), default=0)
    approved = Column(M(), default=0); realised = Column(M(), default=0)
    priority = Column(String, default="Medium"); owner = Column(String)
    review_status = Column(String, default="Pending")   # Pending|Approved|Rejected|Needs Correction
    action_status = Column(String, default="Open")      # Open|In Progress|Fixed|Dismissed
    private_notes = Column(Text)                        # accountant-only
    deleted = Column(Boolean, default=False); created = Column(DateTime, default=now); modified = Column(DateTime, default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("audit_id", "fingerprint"),)
class FindingVersion(Base):
    __tablename__ = "finding_versions"
    id = Column(Integer, primary_key=True); finding_id = Column(ForeignKey("findings.id"), index=True)
    snapshot = Column(JSON); by = Column(String); at = Column(DateTime, default=now)
class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True); finding_id = Column(ForeignKey("findings.id"), index=True)
    author = Column(String); body = Column(Text); at = Column(DateTime, default=now)
class Share(Base):
    __tablename__ = "shared_reports"
    id = Column(Integer, primary_key=True); audit_id = Column(ForeignKey("audits.id"), index=True)
    token_hash = Column(String, unique=True, index=True); expires = Column(DateTime); revoked = Column(Boolean, default=False)
class ApiToken(Base):
    __tablename__ = "mcp_connections"
    id = Column(Integer, primary_key=True); user_id = Column(ForeignKey("users.id")); token_hash = Column(String, unique=True)
    label = Column(String); revoked = Column(Boolean, default=False); last_used = Column(DateTime)
class ToolLog(Base):
    __tablename__ = "mcp_tool_logs"   # never stores raw statements, only tool name + ok/error
    id = Column(Integer, primary_key=True); user_id = Column(Integer); tool = Column(String)
    ok = Column(Boolean); error = Column(String); at = Column(DateTime, default=now)
def init(): Base.metadata.create_all(engine)
