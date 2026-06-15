"""State manager for VK bot flows."""

from typing import Dict, Any, Optional
import datetime


class UserStates:
    """Класс для управления состояниями пользователей."""

    def __init__(self):
        self.form_state: Dict[int, Dict[str, Any]] = {}
        self.sum_input_state: Dict[int, Dict[str, Any]] = {}
        self.master_creation_state: Dict[int, Dict[str, Any]] = {}
        self.order_creation_state: Dict[int, Dict[str, Any]] = {}
        self.city_creation_state: Dict[int, Dict[str, Any]] = {}
        self.director_city_assign: Dict[int, Dict[str, Any]] = {}
        self.city_management_state: Dict[int, str] = {}
        self.master_city_assign: Dict[int, Dict[str, Any]] = {}
        self.assign_state: Dict[int, Dict[str, Any]] = {}
        self.equipment_edit_state: Dict[int, Dict[str, Any]] = {}
        self.cash_cleared_timestamps: Dict[int, datetime.datetime] = {}

    def get_form_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.form_state.get(user_id)

    def set_form_state(self, user_id: int, state: Dict[str, Any]) -> None:
        self.form_state[user_id] = state

    def clear_form_state(self, user_id: int) -> None:
        self.form_state.pop(user_id, None)

    def get_sum_input_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.sum_input_state.get(user_id)

    def set_sum_input_state(self, user_id: int, state: Dict[str, Any]) -> None:
        self.sum_input_state[user_id] = state

    def clear_sum_input_state(self, user_id: int) -> None:
        self.sum_input_state.pop(user_id, None)

    def get_master_creation_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.master_creation_state.get(user_id)

    def set_master_creation_state(self, user_id: int, state: Dict[str, Any]) -> None:
        self.master_creation_state[user_id] = state

    def clear_master_creation_state(self, user_id: int) -> None:
        self.master_creation_state.pop(user_id, None)

    def get_city_creation_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.city_creation_state.get(user_id)

    def set_city_creation_state(self, user_id: int, state: Dict[str, Any]) -> None:
        self.city_creation_state[user_id] = state

    def clear_city_creation_state(self, user_id: int) -> None:
        self.city_creation_state.pop(user_id, None)

    def get_city_management_state(self, user_id: int) -> Optional[str]:
        return self.city_management_state.get(user_id)

    def set_city_management_state(self, user_id: int, state: str) -> None:
        self.city_management_state[user_id] = state

    def clear_city_management_state(self, user_id: int) -> None:
        self.city_management_state.pop(user_id, None)

    def get_director_city_assign(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.director_city_assign.get(user_id)

    def set_director_city_assign(self, user_id: int, state: Dict[str, Any]) -> None:
        self.director_city_assign[user_id] = state

    def clear_director_city_assign(self, user_id: int) -> None:
        self.director_city_assign.pop(user_id, None)

    def get_master_city_assign(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.master_city_assign.get(user_id)

    def set_master_city_assign(self, user_id: int, state: Dict[str, Any]) -> None:
        self.master_city_assign[user_id] = state

    def clear_master_city_assign(self, user_id: int) -> None:
        self.master_city_assign.pop(user_id, None)

    def get_assign_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.assign_state.get(user_id)

    def set_assign_state(self, user_id: int, state: Dict[str, Any]) -> None:
        self.assign_state[user_id] = state

    def clear_assign_state(self, user_id: int) -> None:
        self.assign_state.pop(user_id, None)

    def get_equipment_edit_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.equipment_edit_state.get(user_id)

    def set_equipment_edit_state(self, user_id: int, state: Dict[str, Any]) -> None:
        self.equipment_edit_state[user_id] = state

    def clear_equipment_edit_state(self, user_id: int) -> None:
        self.equipment_edit_state.pop(user_id, None)

    def get_cash_cleared_timestamp(self, city_id: int) -> Optional[datetime.datetime]:
        return self.cash_cleared_timestamps.get(city_id)

    def set_cash_cleared_timestamp(self, city_id: int, timestamp: datetime.datetime) -> None:
        self.cash_cleared_timestamps[city_id] = timestamp

    def clear_all_states(self, user_id: int) -> None:
        self.clear_form_state(user_id)
        self.clear_sum_input_state(user_id)
        self.clear_master_creation_state(user_id)
        self.clear_city_creation_state(user_id)
        self.clear_city_management_state(user_id)
        self.clear_director_city_assign(user_id)
        self.clear_master_city_assign(user_id)
        self.clear_assign_state(user_id)


user_states = UserStates()

FORM_STATE = user_states.form_state
SUM_INPUT_STATE = user_states.sum_input_state
MASTER_CREATION_STATE = user_states.master_creation_state
ORDER_CREATION_STATE = user_states.order_creation_state
DIRECTOR_CITY_ASSIGN = user_states.director_city_assign
CITY_MANAGEMENT_STATE = user_states.city_management_state
MASTER_CITY_ASSIGN = user_states.master_city_assign
ASSIGN_STATE = user_states.assign_state


