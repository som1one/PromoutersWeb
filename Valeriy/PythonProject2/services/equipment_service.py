EQUIP_SETTINGS = {
    'appliance': {'name': 'Бытовая', 'master_pct': 60, 'company_pct': 40},
    'pc': {'name': 'ПК', 'master_pct': 55, 'company_pct': 45},
    'phones': {'name': 'Телевизоры', 'master_pct': 50, 'company_pct': 50},
    'other': {'name': 'Другое', 'master_pct': 60, 'company_pct': 40},
}

def equip_types():
    '''Список всех типов техники для генерации кнопок, фильтрации и статистики.'''
    return [ (v['name'], k) for k, v in EQUIP_SETTINGS.items() ]

def get_pct(type_key):
    s = EQUIP_SETTINGS.get(type_key, {})
    return s.get('master_pct', 60), s.get('company_pct', 40)

def update_equipment_percentage(equip_type, master_pct):
    """Обновить процент мастера для типа техники"""
    if equip_type in EQUIP_SETTINGS:
        EQUIP_SETTINGS[equip_type]['master_pct'] = master_pct
        EQUIP_SETTINGS[equip_type]['company_pct'] = 100 - master_pct