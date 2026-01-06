"""
Fields Parser - Parse nested field attributes from Jira issues
"""
from typing import Any, Dict, List, Optional
import json


def parse_leaf_attribute(attribute: Any, custom_prop: str = None) -> str:
    """Parse a leaf attribute to string"""
    if attribute is None:
        return ''
    elif isinstance(attribute, str):
        return attribute
    elif isinstance(attribute, bool):
        return str(attribute).lower()
    elif isinstance(attribute, (int, float)):
        return str(attribute)
    else:
        # Object
        if custom_prop and isinstance(attribute, dict):
            return str(attribute.get(custom_prop, ''))
        return json.dumps(attribute)


def parse_array(data: List[Any], last_nodes_key: List[str]) -> Any:
    """Parse array values with special handling for 'last' and 'first'"""
    if not data:
        return ''
    
    last_node_key = last_nodes_key[0] if last_nodes_key else None
    
    if last_node_key == 'last':
        return data[-1] if data else None
    elif last_node_key == 'first':
        return data[0] if data else None
    else:
        parsed_values = [parse_leaf_attribute(e, last_node_key) for e in data]
        if len(parsed_values) == 0:
            return ''
        elif len(parsed_values) == 1:
            return parsed_values[0]
        else:
            if last_nodes_key and len(last_nodes_key) >= 2:
                return [parse_leaf_attribute(e, last_nodes_key[1]) for e in parsed_values]
            return json.dumps(parsed_values)


def get_attributes(fields: Dict[str, Any], attributes_requested: List[str]) -> Dict[str, str]:
    """
    Extract requested attributes from Jira issue fields
    
    Args:
        fields: The fields object from a Jira issue
        attributes_requested: List of attribute paths (e.g., 'status.name', 'priority.name')
        
    Returns:
        Dictionary mapping attribute paths to their values
    """
    result = {}
    
    for attribute_system_name in attributes_requested:
        nested_attr_keys = attribute_system_name.split('.')
        
        next_data = dict(fields)  # Clone the fields
        
        i = 0
        while i < len(nested_attr_keys):
            next_node_key = nested_attr_keys[i]
            
            if next_data is None:
                next_data = ''
                break
            
            if not isinstance(next_data, (str, int, float)):
                if isinstance(next_data, dict):
                    next_data = next_data.get(next_node_key)
                else:
                    next_data = ''
                    break
            
            if next_data is not None and isinstance(next_data, list):
                last_nodes_key = nested_attr_keys[i + 1:] if i < len(nested_attr_keys) - 1 else None
                next_data = parse_array(next_data, last_nodes_key)
                if last_nodes_key:
                    i += 1
            
            i += 1
        
        result[attribute_system_name] = parse_leaf_attribute(next_data)
    
    return result

