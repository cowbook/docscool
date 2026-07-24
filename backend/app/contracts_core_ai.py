import json
import re

import requests
from difflib import SequenceMatcher
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import current_app

from .models import Contract
from .contracts_core import (
    AI_AMOUNT_UNIT_TO_YUAN,
    AI_MATCH_CANDIDATE_LIMIT,
    CONTRACT_FIELD_KEYS,
    CSV_OPTION_DEFAULTS,
    EXTERNAL_API_TIMEOUT_SECONDS,
    OPTION_FIELD_DEFAULTS,
    _format_decimal_plain,
    _get_contract_type_options,
    _get_department_names,
    _get_project_names,
    _merge_options,
    _safe_decimal,
)

def _preview_lines(text: str, limit: int = 6):
    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    return lines[:limit]


## OCR相关函数已迁移到ocr_utils.py



## OCR相关函数已迁移到ocr_utils.py



## OCR相关函数已迁移到ocr_utils.py



## OCR相关函数已迁移到ocr_utils.py

def _extract_ai_content(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ''

    output_text = payload.get('output_text')
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    reply = payload.get('reply')
    if isinstance(reply, str):
        return reply

    if isinstance(payload.get('message'), str):
        return payload.get('message')

    choices = payload.get('choices')
    if isinstance(choices, list) and choices:
        message = choices[0].get('message') if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get('content')
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get('text'), str):
                        text_parts.append(item.get('text'))
                if text_parts:
                    return '\n'.join(text_parts)
        text = choices[0].get('text') if isinstance(choices[0], dict) else None
        if isinstance(text, str) and text.strip():
            return text

    data = payload.get('data')
    if isinstance(data, dict) and isinstance(data.get('reply'), str):
        return data.get('reply')

    if isinstance(data, dict):
        nested_choices = data.get('choices')
        if isinstance(nested_choices, list) and nested_choices:
            nested_msg = nested_choices[0].get('message') if isinstance(nested_choices[0], dict) else None
            if isinstance(nested_msg, dict):
                nested_content = nested_msg.get('content')
                if isinstance(nested_content, str) and nested_content.strip():
                    return nested_content

    result = payload.get('result')
    if isinstance(result, str) and result.strip():
        return result

    return ''


def _extract_json_object(text: str) -> dict:
    if not text:
        return {}

    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = stripped.find('{')
    end = stripped.rfind('}')
    if start >= 0 and end > start:
        candidate = stripped[start:end + 1]
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    return {}


def _normalize_date_value(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''

    match = re.search(r'(20\d{2})[-/.年\s]+(\d{1,2})[-/.月\s]+(\d{1,2})', text)
    if not match:
        return text

    year, month, day = match.groups()
    return f'{year}-{int(month):02d}-{int(day):02d}'


def _find_contract_number(pdf_text: str, fallback: str) -> str:
    text = (pdf_text or '').replace(' ', '')
    patterns = [
        r'合同编号[:：]?([A-Za-z]{1,4}\d{2,8}-\d{1,4})',
        r'\b([A-Za-z]{1,4}\d{2,8}-\d{1,4})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()

    cleaned = re.sub(r'[^A-Za-z0-9-]', '', (fallback or '').upper())
    return cleaned


def _find_amount(fallback: str) -> str:
    # 优先解析“数字+单位”（亿/万/千/元），并统一换算成元，最多保留到分。
    text = str(fallback or '').replace(',', '').replace('，', '').strip()
    if not text:
        return ''

    unit_match = re.search(r'([+-]?[0-9]+(?:\.[0-9]+)?)(亿元|万元|千元|万|亿|元)', text)
    if unit_match:
        number_text, unit_text = unit_match.group(1), unit_match.group(2)
        try:
            amount_yuan = Decimal(number_text) * AI_AMOUNT_UNIT_TO_YUAN[unit_text]
            amount_yuan = amount_yuan.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return _format_decimal_plain(amount_yuan)
        except (InvalidOperation, ValueError, KeyError):
            return ''

    # 无单位时按“元”处理，最多保留到分。
    if re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', text):
        try:
            amount_yuan = Decimal(text).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return _format_decimal_plain(amount_yuan)
        except (InvalidOperation, ValueError):
            return ''

    # 兜底清洗，处理如“¥1,234.5元”这类混合字符串。
    cleaned = re.sub(r'[^0-9.+-]', '', text)
    if cleaned.count('.') > 1:
        first_dot = cleaned.find('.')
        cleaned = cleaned[:first_dot + 1] + cleaned[first_dot + 1:].replace('.', '')

    if re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', cleaned):
        try:
            amount_yuan = Decimal(cleaned).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return _format_decimal_plain(amount_yuan)
        except (InvalidOperation, ValueError):
            return ''

    return ''


def _normalize_company_name(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    return re.sub(r'[^\w\u4e00-\u9fff]+', '', text).lower()


def _exclude_my_company(contract_unit: str) -> str:
    my_comp = current_app.config.get('MY_COMP', '')
    if not my_comp:
        return (contract_unit or '').strip()

    parts = [
        part.strip()
        for part in re.split(r'[、,，;；/\\\n]+', contract_unit or '')
        if part and part.strip()
    ]
    if not parts:
        return ''

    my_comp_norm = _normalize_company_name(my_comp)
    kept = [part for part in parts if _normalize_company_name(part) != my_comp_norm]

    if not kept:
        return ''
    return '、'.join(kept)


def _normalize_ai_fields(raw: dict, pdf_text: str = '') -> dict:
    normalized = {}
    for key in CONTRACT_FIELD_KEYS:
        value = raw.get(key) if isinstance(raw, dict) else None
        if value is None:
            normalized[key] = ''
        elif isinstance(value, (int, float)):
            normalized[key] = str(value)
        else:
            normalized[key] = str(value).strip()

    normalized['contract_number'] = _find_contract_number(pdf_text, normalized.get('contract_number', ''))
    normalized['contract_unit'] = _exclude_my_company(normalized.get('contract_unit', ''))
    
    normalized['contract_amount'] = _find_amount(normalized.get('contract_amount', ''))

    normalized['handling_date'] = _normalize_date_value(normalized.get('handling_date', ''))
    
    return normalized


def _normalize_option_text(value: str) -> str:
    text = (value or '').strip().lower()
    return re.sub(r'[^\w\u4e00-\u9fff]+', '', text)


def _find_ai_match_candidates(fields: dict, limit: int = AI_MATCH_CANDIDATE_LIMIT):
    normalized_name = _normalize_option_text((fields or {}).get('contract_name', ''))
    amount = _safe_decimal((fields or {}).get('contract_amount'))
    if not normalized_name and amount is None:
        return []

    same_amount_candidates = []
    name_similarity_candidates = []
    rows = Contract.query.order_by(Contract.updated_at.desc()).all()
    for row in rows:
        reasons = []
        similarity = 0.0
        contains_match = False

        existing_name = _normalize_option_text(row.contract_name or '')
        if normalized_name and existing_name:
            similarity = SequenceMatcher(None, normalized_name, existing_name).ratio()
            contains_match = normalized_name in existing_name or existing_name in normalized_name
            if contains_match or similarity >= 0.55:
                reasons.append('标题相似')

        same_amount = False
        if amount is not None and row.amount is not None:
            try:
                same_amount = Decimal(str(row.amount)) == amount
            except (InvalidOperation, ValueError):
                same_amount = False
            if same_amount:
                reasons.append('金额相同')

        if not reasons:
            continue

        item = row.to_dict()
        item['match_reasons'] = reasons
        item['name_similarity'] = round(similarity, 4)
        item['same_amount'] = same_amount

        if same_amount:
            same_amount_candidates.append(item)
        elif contains_match or similarity >= 0.55:
            name_similarity_candidates.append(item)

    same_amount_candidates.sort(key=lambda item: (-item['name_similarity'], -item['id']))
    name_similarity_candidates.sort(key=lambda item: (-item['name_similarity'], -item['id']))

    merged = []
    seen_ids = set()
    for item in same_amount_candidates:
        if item['id'] in seen_ids:
            continue
        merged.append(item)
        seen_ids.add(item['id'])

    for item in name_similarity_candidates[:5]:
        if item['id'] in seen_ids:
            continue
        merged.append(item)
        seen_ids.add(item['id'])

    return merged[:limit]


def _match_option_value(value: str, options, default: str = '') -> str:
    candidates = [item for item in (options or []) if str(item).strip()]
    if not candidates:
        return default

    raw = (value or '').strip()
    if not raw:
        return default

    if raw in candidates:
        return raw

    norm_raw = _normalize_option_text(raw)
    if not norm_raw:
        return default

    for item in candidates:
        if _normalize_option_text(item) == norm_raw:
            return item

    best = ''
    best_score = 0
    for item in candidates:
        norm_item = _normalize_option_text(item)
        if not norm_item:
            continue
        if norm_item in norm_raw or norm_raw in norm_item:
            score = min(len(norm_item), len(norm_raw))
            if score > best_score:
                best = item
                best_score = score

    if best:
        return best
    return default


def _get_contract_option_sets() -> dict:
    option_sets = {
        key: list(CSV_OPTION_DEFAULTS.get(key, []))
        for key in CSV_OPTION_DEFAULTS.keys()
    }
    option_sets['contract_type'] = _get_contract_type_options()
    option_sets['handling_department'] = _get_department_names()
    option_sets['project'] = _merge_options(_get_project_names(), [OPTION_FIELD_DEFAULTS['project']])
    return option_sets


def _normalize_option_fields(fields: dict) -> dict:
    option_sets = _get_contract_option_sets()
    normalized = dict(fields or {})

    normalized['handling_department'] = _match_option_value(
        normalized.get('handling_department', ''),
        option_sets.get('handling_department', []),
        '',
    )
    normalized['contract_form'] = _match_option_value(
        normalized.get('contract_form', ''),
        option_sets.get('contract_form', []),
        OPTION_FIELD_DEFAULTS['contract_form'],
    )
    normalized['project'] = _match_option_value(
        normalized.get('project', ''),
        option_sets.get('project', []),
        OPTION_FIELD_DEFAULTS['project'],
    )


    normalized['contract_determination_method'] = _match_option_value(
        normalized.get('contract_determination_method', ''),
        option_sets.get('contract_determination_method', []),
        OPTION_FIELD_DEFAULTS['contract_determination_method'],
    )


    normalized['contract_type'] = _match_option_value(
        normalized.get('contract_type', ''),
        option_sets.get('contract_type', []),
        '',
    )


    normalized['purchase_type'] = _match_option_value(
        normalized.get('purchase_type', ''),
        option_sets.get('purchase_type', []),
        '',
    )
    normalized['pricing_method'] = _match_option_value(
        normalized.get('pricing_method', ''),
        option_sets.get('pricing_method', []),
        '',
    )
    normalized['is_archived'] = _match_option_value(
        normalized.get('is_archived', ''),
        option_sets.get('is_archived', []),
        OPTION_FIELD_DEFAULTS['is_archived'],
    )
    return normalized


def _has_any_field_value(fields: dict) -> bool:
    if not isinstance(fields, dict):
        return False
    return any(str(fields.get(key, '')).strip() for key in CONTRACT_FIELD_KEYS)


def _minimax_extract_fields(pdf_text: str) -> dict:

    #print('pdf_text:', pdf_text[:2000])

    api_key = (current_app.config.get('MINIMAX_API_KEY') or '').strip()
    if not api_key:
        raise RuntimeError('MINIMAX_API_KEY 未配置')

    api_url = (current_app.config.get('MINIMAX_API_URL') or '').strip()
    model = (current_app.config.get('MINIMAX_MODEL') or '').strip()

    prompt = (
        'contract_type指的是合同类型，值在如下选择：' + ','.join(CSV_OPTION_DEFAULTS['contract_type']) + '。必须要返回内容，如果文本没有明确写出类型，请按印花税合同分类选择最贴近的一项：设备材料采购/销售归为买卖合同，贷款融资归为借款合同，房屋设备租用归为租赁合同，委托加工制作归为承揽合同，施工建设归为建设工程合同，货物物流承运归为运输合同，技术开发转让咨询服务归为技术合同，代保管归为保管合同，仓储服务归为仓储合同，保险保单归为财产保险合同。\n'
            'contract_form指的是合同形式，值在如下选择：' + ','.join(CSV_OPTION_DEFAULTS['contract_form']) + '。必须要返回内容，如果文本没有明确写出形式，请根据上下文判断是新签合同、补充合同、补充协议还是变更合同。\n'
        'purchase_type指的是采购类型，值在如下选择：' + ','.join(CSV_OPTION_DEFAULTS['purchase_type']) + '。必须要返回内容，按合同业务性质归类：工程施工建设归工程类，咨询运维检测培训等归服务类，设备材料货物采购归采购类，不属于采购项目或与采购无关归非采购类。\n'
        'stamp_tax_rate指的是印花税率，请根据合同类型返回税法规定税率：买卖合同0.03%，借款合同0.005%，租赁合同0.1%，承揽合同0.03%，建设工程合同0.03%，运输合同0.03%，技术合同0.03%，保管合同0.1%，仓储合同0.1%，财产保险合同0.1%，其他类型可返回空字符串。\n'
        'pricing_method指的是合同的计价方式，值在如下选择：' + ','.join(CSV_OPTION_DEFAULTS['pricing_method']) + '。必须要返回内容，如果找不到就请总结提炼这个合同可能是通过什么方式计价的，如果讲到了综合单价暂定工程量就是单价合同，其它默认都返回总价合同。\n'
        'contract_determination_method指的是合同是如何确定的，值在如下选择：' + ','.join(CSV_OPTION_DEFAULTS['contract_determination_method']) + '，必须要返回内容，如果找不到就请总结提炼这个合同可能是通过什么方式确定的。\n'
        'contract_name指的是合同名称或标题，必须要返回内容，一般会出现在文本的前几行，如果找不到就请总结合同标题， 如果某字段找不到准确的文本，请尽量根据上下文来总结提炼。\n'
        'handling_date格式为 YYYY-MM-DD。\n'
        'contract_unit指的是对方的公司，因此不能返回我方公司名称“' + (current_app.config.get('MY_COMP') or '') + '”及其常见变体，如果不好定位就返回文本里出现的非我公司的单位名称。\n'
        'contract_amount 指的是合同金额（人民币元）返回以为元单位的纯数字字符串，如果合同文本中带单位，如果原文是万元、亿元等其它单位返回时带上万、亿\n'
        'project是合同属于什么工程或项目，请尽量从标题或是其它文本中识别出项目相关信息， 从全文解理本合同是不是属于如下项目列表，不需要要强匹配找意思相似的标题或文本, 必须值返回如下的项目名称文本，如果合同真的不属于项目或是工程请返回空""：'+ ','.join(_get_project_names()) + '。\n' 
        'handling_department必须返回如下的部门列表其中之一文本（如果能从标题或是其它文本中识别出部门相关信息的话最好，不能的话先判断这个合同一般是列表中的哪个部门职责，通过判断来返回），实在靠不上部门请返回空""：' + ','.join(_get_department_names()) + '。\n'
        '以下是PDF文本：\n'
        + pdf_text[:20000]
    )

    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': '你是PDF扫描合同得出文本的结构化抽取专家，请从给定PDF扫描出来的合同文本，该合同文本是从图像识别出来没有经过加工肯定包含意外的回车、噪声、格式和语序问题。只抽取合同字段，并只返回JSON对象，不要输出任何解释。你是合同结构化抽取助手，只返回合法JSON对象，不输出解释。'
                '返回的JSON键必须严格使用以下字段：'
                +','.join(CONTRACT_FIELD_KEYS)
                + '\n'
                   
            },
            {
                'role': 'user',
                'content': prompt,
            },
        ],
        'temperature': 0.2,
        'max_tokens': 1024,
        'stream': False,
    }


    #print('payload:',payload)

    current_app.logger.info(
        'AI parse: Minimax request model=%s text_chars=%s prompt_chars=%s',
        model,
        len(pdf_text),
        len(prompt),
    )

    response = requests.post(
        api_url,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=EXTERNAL_API_TIMEOUT_SECONDS,
    )
    current_app.logger.info('AI parse: Minimax response status=%s', response.status_code)
    response.raise_for_status()

    response_payload = response.json()
    current_app.logger.info('AI parse: Minimax payload keys=%s', sorted(list(response_payload.keys())))
    base_resp = response_payload.get('base_resp')
    
    if isinstance(base_resp, dict):
        current_app.logger.info('AI parse: Minimax base_resp=%s', base_resp)
        status_code = base_resp.get('status_code')
        if status_code not in (0, None):
            raise RuntimeError(f"Minimax接口错误: {base_resp.get('status_msg') or status_code}")

    content = _extract_ai_content(response_payload)


    current_app.logger.info('AI parse: Minimax content chars=%s snippet=%s', len(content), (content or '')[:200])
    if not content.strip():
        raise RuntimeError('Minimax返回成功但无可用文本内容')

    parsed = _extract_json_object(content)
    current_app.logger.info('AI parse: Minimax parsed keys=%s', sorted(list(parsed.keys())) if isinstance(parsed, dict) else [])
    return _normalize_ai_fields(parsed, pdf_text)


## OCR相关函数已迁移到ocr_utils.py



## OCR相关函数已迁移到ocr_utils.py



