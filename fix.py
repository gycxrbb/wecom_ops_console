import re

with open('app/routers/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix serialize_material
content = re.sub(
    r"def serialize_material\(material: models\.Material\):\s+return \{\s+'id': asset\.id,\s+'name': asset\.name,\s+'asset_type': asset\.asset_type,\s+'file_name': asset\.file_name,\s+'mime_type': asset\.mime_type,\s+'size': asset\.size,\s+'url': f'/api/assets/\{asset\.id\}/download',\s+'created_at': asset\.created_at\.isoformat\(\),\s+\}",
    '''def serialize_material(material: models.Material):
    return {
        'id': material.id,
        'name': material.name,
        'material_type': material.material_type,
        'mime_type': material.mime_type,
        'file_size': material.file_size,
        'url': f'/api/v1/assets/{material.id}/download',
        'created_at': material.created_at.isoformat(),
    }''',
    content, flags=re.MULTILINE
)

# Fix upload_asset
content = content.replace(
    '''asset = models.Material(name=Path(file.filename).stem, asset_type=asset_type, file_name=file.filename, stored_path=str(stored_path), mime_type=file.content_type or 'application/octet-stream', size=stored_path.stat().st_size, owner_id=user.id)''',
    '''asset = models.Material(name=Path(file.filename).name, material_type=asset_type, storage_path=str(stored_path), mime_type=file.content_type or 'application/octet-stream', file_size=stored_path.stat().st_size, owner_id=user.id)'''
)

# Fix download route to use storage_path instead of stored_path
content = content.replace('asset.stored_path', 'asset.storage_path')

with open('app/routers/api.py', 'w', encoding='utf-8') as f:
    f.write(content)
