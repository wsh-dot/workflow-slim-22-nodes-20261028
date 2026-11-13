"""Pin 0902 execution semantics to a task; reject changed resumes and disabled writes."""
import hashlib
import json
from pathlib import Path



def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str, allow_nan=False).encode('utf-8')).hexdigest()


# Existing unversioned tasks at the removal boundary must never adopt new code on retry.
def require_frozen_profile(record, task):
    """Validate the task-owned record without accepting a missing or retired version."""
    if not isinstance(record, dict) or record.get('schema_version') != '1.0':
        raise ValueError('任务执行版本记录缺失或格式无效，禁止重新认领新版本')
    if record.get('state') == 'RETIRED':
        raise ValueError('历史任务已退役或缺少冻结版本，需明确新的任务边界')
    if record.get('state') != 'FROZEN' or not isinstance(record.get('profile_data'), dict):
        raise ValueError('任务执行版本记录格式无效')
    if (record.get('project_id'), record.get('batch_id')) != (task['project_id'], task['batch_id']):
        raise ValueError('任务冻结配置归属已变化，拒绝混用')
    if record.get('profile_fingerprint') != digest(record['profile_data']):
        raise ValueError('任务执行版本指纹与正文不一致，拒绝损坏记录')
    return record['profile_fingerprint']


ROOT = Path(__file__).parent
def code_manifest():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(ROOT.glob('*.py'))}


LOADED_CODE = code_manifest()


def execution_profile(config, cbs):
    if code_manifest() != LOADED_CODE:
        raise ValueError('磁盘源码与本进程启动版本不同，必须先安全重启，不能用新指纹冒充旧进程')
    root = Path(__file__).parent
    files = list(root.glob('*.py')) + list(config.prompt_dir.glob('*.txt')) + list(config.prompt_dir.glob('*.json'))
    files += list((root / 'schemas').glob('*.json')) + list(root.glob('requirements*.txt'))
    sources = {str(path.relative_to(root)) if path.is_relative_to(root) else str(path):
               hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)}
    model = {key: value for key, value in config.model.items() if key != 'api_key'}
    model['credential_fingerprint'] = hashlib.sha256(config.model.get('api_key', '').encode()).hexdigest()
    return {'protocol': '0902-full-object-v1', 'sources': sources,
            'loaded_code': LOADED_CODE, 'model': model, 'analysis_options': config.analysis_options, 'business': config.business,
            'rules_fingerprint': digest(config.classification_rules), 'cbs_fingerprint': digest(cbs)}
