import json
import re

def extract_components(text):
    thought_pattern = r'\*\*Thought\*\*: (.*?)\n'
    action_name_pattern = r'```(.*?)\n'
    action_params_pattern = r'```.*?\n(.*?)```'
    expected_info_pattern = r'\*\*Expected Information\*\*: (.*?)\n'
    
    pair_pattern = r'#### Thought-Action Pair (TA\d+)(.*?)(?=#### Thought-Action Pair TA\d+|\Z)'
    pairs = re.findall(pair_pattern, text, re.DOTALL)
    
    results = []
    
    for pair_id, pair_content in pairs:
        thought_match = re.search(thought_pattern, pair_content)
        action_name_match = re.search(action_name_pattern, pair_content)
        action_params_match = re.search(action_params_pattern, pair_content, re.DOTALL)
        expected_info_match = re.search(expected_info_pattern, pair_content)
        
        if thought_match and action_name_match and action_params_match and expected_info_match:
            try:
                action_params_json = json.loads(action_params_match.group(1).strip())
            except json.JSONDecodeError:
                action_params_json = {"error": "Invalid JSON"}
            
            pair_dict = {
                "id": pair_id.strip(),
                "thought": thought_match.group(1).strip(),
                "action_name": action_name_match.group(1).strip(),
                "action_parameters": action_params_json,
                "expected_information": expected_info_match.group(1).strip()
            }
            
            results.append(pair_dict)

# 示例文本
text = '''
### Exploration Step 2                                                                                  
                                                                                                                                                                 
#### Thought-Action Pair TA004                                                                                                                                   
- **Thought**: Since the `load_module` function has been modified, I need to understand how it interacts with other components in the system to ensure that all d
ependencies are correctly handled.                                                                                                                               
- **Action**: search_code_dependencies                                                                                                                           
- **Action Parameters**: {"entity_name": "load_module"}                                                                                                          
- **Expected Information**: This will help me identify which functions or classes call `load_module` and which functions it calls, allowing me to understand the 
broader impact of these changes.                                                                                                                                 
                                                                                                                                                                 
#### Thought-Action Pair TA005                                                                                                                                   
- **Thought**: The PR involves changes to the deck configuration, specifically the introduction of fixture definitions for modules. I need to understand how thes
e changes affect the overall deck configuration validation.                                                                                                      
- **Action**: search_class_in_project                                                                                                                            
- **Action Parameters**: {"class_name": "DeckConfiguration"}                                                                                                     
- **Expected Information**: This will provide details about the `DeckConfiguration` class, including its methods and properties, which are likely involved in val
idating the new fixture definitions.                                                                                                                             
                                                                                                                                                                 
#### Thought-Action Pair TA006                                                                                                                                   
- **Thought**: The PR includes updates to the `/deck_configuration` endpoint. I need to examine the changes to this endpoint to understand how it handles module 
fixtures.                                                                                                                                                        
- **Action**: view_code_changes                                                                                                                                  
- **Action Parameters**: {"file_path": "api/src/opentrons/calibration_storage/deck_configuration.py"}                                                            
- **Expected Information**: This will show me the exact changes made to the endpoint, including any new functionality or modifications to existing logic.        
                                                                                                                                                                 
#### Thought-Action Pair TA007                                                                                                                                   
- **Thought**: The PR modifies several files related to the protocol engine and state management. I need to understand how these changes affect the overall state
 management and validation of deck configurations.                                                                                                               
- **Action**: search_class_in_project                                                                                                                            
- **Action Parameters**: {"class_name": "State"}                                                                                                                 
- **Expected Information**: This will help me understand the `State` class, which is likely central to managing and validating deck configurations, including the
 new fixture definitions.                                                                                                                                        
                                                                                                                                                                 
#### Thought-Action Pair TA008                                                                                                                                   
- **Thought**: The PR includes changes to the `types.py` files in both the `calibration_storage` and `protocol_engine` directories. I need to examine these chang
es to understand how they impact the type definitions used throughout the system.                                                                                
- **Action**: view_code_changes                                                                                                                                  
- **Action Parameters**: {"file_path": "api/src/opentrons/calibration_storage/types.py"}
- **Expected Information**: This will show me the changes to the type definitions, which are crucial for ensuring consistency and correctness across the system.
'''

result = extract_components(text)
result
