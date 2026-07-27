from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import json

from .extensions import db


def _decimal_to_string(value) -> str:
    if value is None:
        return ''

    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    # Normalize money output to 2 decimals to avoid SQLite float artifacts like 0.19999999.
    normalized = decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return format(normalized, 'f')


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer, primary_key=True)
    contract_number = db.Column(db.String(64), unique=True, nullable=True, index=True)
    contract_name = db.Column(db.String(255), nullable=False)
    contract_unit = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(20, 8), nullable=True)
    currency = db.Column(db.String(16), nullable=False, default='CNY')
    handler = db.Column(db.String(64), nullable=True)
    department = db.Column(db.String(128), nullable=False, index=True)
    current_management_department = db.Column(db.String(128), nullable=True)
    contract_form = db.Column(db.String(32), nullable=True)
    contract_determination_method = db.Column(db.String(64), nullable=True)
    handling_date = db.Column(db.Date, nullable=True)
    contract_type = db.Column(db.String(64), nullable=True)
    purchase_type = db.Column(db.String(64), nullable=True)
    stamp_tax_rate = db.Column(db.String(32), nullable=True)
    pricing_method = db.Column(db.String(64), nullable=True)
    copy_count = db.Column(db.Integer, nullable=True)
    save_place = db.Column(db.String(50), nullable=True)
    is_archived = db.Column(db.String(32), nullable=True)
    color_flag = db.Column(db.String(32), nullable=True)
    completeness = db.Column(db.String(4), nullable=True)
    project = db.Column(db.String(255), nullable=True)
    original_contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True, index=True)
    fullbody = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(32), nullable=False, default='active')
    file_path = db.Column(db.String(512), nullable=True)
    created_by = db.Column(db.String(128), nullable=False)
    updated_by = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    original_contract = db.relationship(
        'Contract',
        remote_side=[id],
        foreign_keys=[original_contract_id],
        uselist=False,
    )

    def to_dict(self, include_fullbody: bool = False):
        payload = {
            'id': self.id,
            'contract_number': self.contract_number,
            'contract_name': self.contract_name,
            'contract_unit': self.contract_unit,
            'contract_amount': _decimal_to_string(self.amount),
            'amount': _decimal_to_string(self.amount),
            'currency': self.currency,
            'handler': self.handler,
            'handling_department': self.department,
            'department': self.department,
            'current_management_department': self.current_management_department,
            'contract_form': self.contract_form,
            'contract_determination_method': self.contract_determination_method,
            'handling_date': self.handling_date.isoformat() if self.handling_date else None,
            'contract_type': self.contract_type,
            'purchase_type': self.purchase_type,
            'stamp_tax_rate': self.stamp_tax_rate,
            'pricing_method': self.pricing_method,
            'copy_count': self.copy_count,
            'save_place': self.save_place,
            'is_archived': self.is_archived,
            'color_flag': self.color_flag,
            'completeness': self.completeness,
            'project': self.project,
            'original_contract_id': self.original_contract_id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status,
            'file_path': self.file_path,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        if include_fullbody:
            payload['fullbody'] = self.fullbody or ''
            payload['original_contract'] = None
            if self.original_contract is not None:
                payload['original_contract'] = {
                    'id': self.original_contract.id,
                    'contract_number': self.original_contract.contract_number,
                    'contract_name': self.original_contract.contract_name,
                }
        return payload


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    is_existing = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text('1'))
    current_department_name = db.Column(db.String(50), nullable=True)
    principal_login_name = db.Column(db.String(128), nullable=True)
    handler_login_name = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_existing': bool(self.is_existing),
            'current_department_name': self.current_department_name or '',
            'principal_login_name': self.principal_login_name or '',
            'handler_login_name': self.handler_login_name or '',
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


class StampTaxRateOption(db.Model):
    __tablename__ = 'stamp_tax_rate_options'

    id = db.Column(db.Integer, primary_key=True)
    contract_type = db.Column(db.String(64), unique=True, nullable=False, index=True)
    tax_rate = db.Column(db.String(32), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'contract_type': self.contract_type,
            'tax_rate': self.tax_rate,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class UserPermission(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    login_name = db.Column(db.String(128), unique=True, nullable=False, index=True)
    me_added = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text('0'))
    description = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(32), nullable=False, default='admin', server_default='admin')
    permission_list = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def _normalize_text_list(value):
        source = value if isinstance(value, list) else []
        normalized = []
        seen = set()
        for item in source:
            text = str(item or '').strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def get_permission_items(self):
        try:
            parsed = json.loads(self.permission_list) if self.permission_list else []
        except Exception:
            parsed = []

        normalized = []
        for item in parsed if isinstance(parsed, list) else []:
            if not isinstance(item, dict):
                continue
            permission = str(item.get('permission') or '').strip()
            if permission not in {'edit', 'view'}:
                continue

            departments = self._normalize_text_list(item.get('departments'))
            folders = self._normalize_text_list(item.get('folders'))

            normalized.append({
                'permission': permission,
                'departments': departments,
                'folders': folders,
            })

        if normalized:
            return normalized

        return [{
            'permission': 'view',
            'departments': [],
            'folders': [],
        }]

    def get_aggregated_permission(self):
        items = self.get_permission_items()
        permission = 'view'
        departments = []
        folders = []

        dep_seen = set()
        folder_seen = set()
        for item in items:
            value = str(item.get('permission') or '').strip()
            if value == 'edit':
                permission = 'edit'

            for dep in self._normalize_text_list(item.get('departments')):
                if dep not in dep_seen:
                    dep_seen.add(dep)
                    departments.append(dep)

            for folder in self._normalize_text_list(item.get('folders')):
                if folder not in folder_seen:
                    folder_seen.add(folder)
                    folders.append(folder)

        return {
            'permission': permission,
            'departments': departments,
            'folders': folders,
        }

    def get_role(self):
        value = str(self.role or 'admin').strip()
        return value if value in {'super_admin', 'admin', 'synology_super_admin'} else 'admin'

    def set_permission_items(self, items):
        normalized = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            permission = str(item.get('permission') or '').strip()
            if permission not in {'edit', 'view'}:
                continue

            departments = self._normalize_text_list(item.get('departments'))
            folders = self._normalize_text_list(item.get('folders'))

            normalized.append({
                'permission': permission,
                'departments': departments,
                'folders': folders,
            })

        if not normalized:
            normalized = [{
                'permission': 'view',
                'departments': [],
                'folders': [],
            }]

        self.permission_list = json.dumps(normalized, ensure_ascii=False)

    def to_dict(self):
        aggregated = self.get_aggregated_permission()
        permission_items = self.get_permission_items()
        return {
            'id': self.id,
            'login_name': self.login_name,
            'me_added': bool(self.me_added),
            'description': self.description or '',
            'role': self.get_role(),
            'permission': aggregated['permission'],
            'departments': ','.join(aggregated['departments']),
            'department_list': aggregated['departments'],
            'folders': ','.join(aggregated['folders']),
            'folder_list': aggregated['folders'],
            'permission_list': permission_items,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class UserLog(db.Model):
    __tablename__ = 'user_log'

    id = db.Column(db.Integer, primary_key=True)
    record_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    operation_module = db.Column(db.String(64), nullable=False)
    operation_target = db.Column(db.String(255), nullable=False)
    operation_type = db.Column(db.String(32), nullable=False)
    detail = db.Column(db.Text, nullable=False, default='')
