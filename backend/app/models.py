from datetime import datetime

from .extensions import db


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer, primary_key=True)
    contract_number = db.Column(db.String(64), unique=True, nullable=True, index=True)
    contract_name = db.Column(db.String(255), nullable=False)
    contract_unit = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(16), nullable=False, default='CNY')
    approval_status = db.Column(db.String(64), nullable=True)
    handler = db.Column(db.String(64), nullable=True)
    department = db.Column(db.String(128), nullable=False, index=True)
    contract_determination_method = db.Column(db.String(64), nullable=True)
    handling_date = db.Column(db.Date, nullable=True)
    contract_type = db.Column(db.String(64), nullable=True)
    invoice_type = db.Column(db.String(64), nullable=True)
    tax_rate = db.Column(db.String(16), nullable=True)
    pricing_method = db.Column(db.String(64), nullable=True)
    is_archived = db.Column(db.String(32), nullable=True)
    project = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(32), nullable=False, default='active')
    file_path = db.Column(db.String(512), nullable=True)
    created_by = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'contract_number': self.contract_number,
            'contract_name': self.contract_name,
            'contract_unit': self.contract_unit,
            'contract_amount_wan': float(self.amount),
            'amount': float(self.amount),
            'currency': self.currency,
            'approval_status': self.approval_status,
            'handler': self.handler,
            'handling_department': self.department,
            'department': self.department,
            'contract_determination_method': self.contract_determination_method,
            'handling_date': self.handling_date.isoformat() if self.handling_date else None,
            'contract_type': self.contract_type,
            'invoice_type': self.invoice_type,
            'tax_rate': self.tax_rate,
            'pricing_method': self.pricing_method,
            'is_archived': self.is_archived,
            'project': self.project,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status,
            'file_path': self.file_path,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
        }


class ProjectOption(db.Model):
    __tablename__ = 'project_options'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
        }
