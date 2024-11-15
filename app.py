import os
import asyncio
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import autogen
from autogen import AssistantAgent, UserProxyAgent,config_list_from_json
import queue
import pyodbc
from typing import Dict, Any, Tuple, List, Optional
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global variables
chat_status = "ended"
print_queue = queue.Queue()
user_queue = queue.Queue()

# Database configuration
DB_CONNECTION_STRING = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=LAPTOP-35ABR8OB;DATABASE=InventoryControlDB;UID=sa;PWD=vesper"

# Update your function configurations
def save_function_config():
    return {
        "type": "function",  # Add this line
        "function": {        # Wrap in function object
            "name": "save_item_to_db",
            "description": "Save an item to the database using the provided information",
            "parameters": {
                "type": "object",
                "properties": {
                    "entries": {
                        "type": "array",
                        "description": "List of item details in order: item code, item description, unit ID, cost price, selling price",
                        "items": {
                            "type": "string"
                        },
                        "minItems": 5,
                        "maxItems": 5
                    }
                },
                "required": ["entries"]
            }
        }
    }

def get_items_function_config():
    return {
        "type": "function",  # Add this line
        "function": {        # Wrap in function object
            "name": "get_items_from_db",
            "description": "Retrieve items from the database",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_params": {
                        "type": "object",
                        "description": "Optional search parameters",
                        "additionalProperties": True
                    }
                }
            }
        }
    }

# The rest of your llm_config remains the same
llm_config = {
    "config_list": config_list_from_json(env_or_file="OAI_CONFIG_LIST"),
    "cache_seed": 42,
    "tools": [save_function_config(), get_items_function_config()]
}


class ChatSession:
    def __init__(self):
        self.messages = []

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def get_messages(self):
        return self.messages

chat_session = ChatSession()

#--------------------------DB  operations----------------------------

def db_connect() -> pyodbc.Connection:
    return pyodbc.connect(DB_CONNECTION_STRING)

def execute_db_operation(query: str, params: Tuple = (), fetch: bool = False) -> Any:
    try:
        with db_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if fetch:
                    columns = [column[0] for column in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
                else:
                    conn.commit()
                    return cursor.rowcount
    except pyodbc.Error as e:
        print(f"Database error: {str(e)}")
        return None
    except Exception as e:
        print(f"Error executing database operation: {str(e)}")
        return None

def save_item_to_db(entries: dict) -> str:
    """Save item to the database using the entered Unit ID directly."""
    if not isinstance(entries, dict) or 'entries' not in entries or not isinstance(entries['entries'], list):
        return "Error: Invalid input format"

    item_data = {}
    keys = ['item_code', 'item_description', 'unit_id', 'cost_price', 'selling_price']
    
    for i, entry in enumerate(entries['entries']):
        if ': ' in entry:
            key, value = entry.split(': ', 1)
            item_data[key.strip().lower()] = value.strip()
        else:
            item_data[keys[i]] = entry.strip()

    if not all(key in item_data for key in keys):
        return "Error: Missing required fields"

    query = """
        INSERT INTO ItemMaster (ItemCode, ItemDescription, UnitID, CostPrice, SellingPrice, UserCreated, UserModified)
        VALUES (?, ?, ?, ?, ?, 'System', 'System')
    """
    params = (
        item_data['item_code'],
        item_data['item_description'],
        item_data['unit_id'],
        float(item_data['cost_price']),
        float(item_data['selling_price'])
    )

    result = execute_db_operation(query, params)
    return "Item saved successfully to the database." if result else "Error saving item to database."

save = {
    "name": "save_item_to_db",
    "description": "Save an item to the database using the provided information",
    "parameters": {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "description": "List of item details in order: item code, item description, unit ID, cost price, selling price",
                "items": {
                    "type": "string"
                },
                "minItems": 5,
                "maxItems": 5
            }
        },
        "required": ["entries"]
    }
}


def delete_item_from_db(item_code: str) -> bool:
    """
    Delete an item from the database.
    
    Args:
        item_code (str): The item code to delete
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        query = "DELETE FROM ItemMaster WHERE ItemCode = ?"
        result = execute_db_operation(query, (item_code,))
        return result > 0
    except Exception as e:
        print(f"Error deleting item: {str(e)}")
        return False

def update_item_in_db(item_code: str, item_data: dict) -> bool:
    """
    Update an existing item in the database.
    
    Args:
        item_code (str): The item code to update
        item_data (dict): Dictionary containing the updated values
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        update_fields = []
        params = []
        
        for key, value in item_data.items():
            if key != 'ItemCode' and value is not None:
                update_fields.append(f"{key} = ?")
                params.append(value)
        
        # Add UserModified and item_code
        update_fields.append("UserModified = ?")
        params.extend(['System', item_code])
        
        query = f"""
            UPDATE ItemMaster 
            SET {', '.join(update_fields)}
            WHERE ItemCode = ?
        """
        
        result = execute_db_operation(query, tuple(params))
        return result > 0
    except Exception as e:
        print(f"Error updating item: {str(e)}")
        return False


def get_items_from_db(item_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve item(s) from the database."""
    query = """
        SELECT ItemID, ItemCode, ItemDescription, UnitID, CostPrice, SellingPrice
        FROM ItemMaster
        {where_clause}
    """
    where_clause = "WHERE ItemID = ?" if item_id is not None else ""
    query = query.format(where_clause=where_clause)
    params = (item_id,) if item_id is not None else ()

    return execute_db_operation(query, params, fetch=True) or []

#--------------------------Agent configuration----------------------------

assistant = autogen.AssistantAgent(
    name="assistant",
    system_message = """You are an AI assistant designed to perform CRUD (Create, Read, Update, Delete) operations on an inventory item database. Your primary focus is on the ItemMaster table, managing item information efficiently and accurately.

Your main responsibilities include:

1. Collect and manage the following information for each item:
   - item_code
   - item_description
   - unit_id
   - cost_price (as a float)
   - selling_price (as a float)

2. Perform the following CRUD operations:
   - Create: Add new items to the database
   - Read: Retrieve item information from the database
   - Update: Modify existing item information
   - Delete: Remove items from the database (if implemented)

3. Allow users to modify any information at any point during the collection process.
4. Keep track of which information has been collected and which needs to be collected or modified.
5. After successfully collecting all information for a new item or updates for an existing item, reply with "Save" to trigger the save process.
6. If any errors occur during the save process, retry the operation and inform the user if it doesn't succeed.
7. If the save is successful, inform the user and proceed to ask if they want to perform another operation (e.g., add a new item, update an existing item, or retrieve item information).

Guidelines for interaction:
- Ask for each piece of information individually, clearly indicating which information you're requesting.
- If the user requests to change previously entered information, promptly ask for the new value and update the item data.
- After modifying information, continue with the next uncollected information or confirm if all information is complete.
- Maintain a clear count of valid information and inform the user of their progress.
- Before replying with "Save", confirm with the user that all entered information is correct.
- Use clear and concise language when asking for input or providing information about database operations.

Remember: Your goal is to ensure all item information is collected and managed accurately according to the user's inputs before proceeding with database operations.

To save item data, use the save_item_to_db(entries: Dict[str, List[str]]) function. The entries should be formatted as follows:
entries = {
    "entries": [
        "item_code: ABC123",
        "item_description: Sample Item",
        "unit_id: 4",
        "cost_price: 45.50",
        "selling_price: 65.75"
    ]
}

For retrieving items, use get_items_from_db(item_id: Optional[int] = None).
For updating items, use update_item_in_db(item_id: int, updates: Dict[str, Any]).

Always confirm the success or failure of database operations with the user and offer to perform additional operations or provide further assistance.""",
    llm_config=llm_config,
    function_map={
        "save_item_to_db": save_item_to_db}
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="TERMINATE",
    max_consecutive_auto_reply=10,
    function_map={"save": save},
    llm_config=llm_config,
     
    code_execution_config={"work_dir": "coding", "use_docker": False},
    system_message="""You are a user proxy that can interact with a human user and automatically execute functions when suggested by the assistant. 
    When the assistant suggests calling a function, you should execute it automatically."""
)

# autogen.register_function(
#     save_item_to_db,
#     caller=assistant,
#     executor=user_proxy,
#     name="save_item_to_db",
#     description="Save collected item details to the database."
# )

# autogen.register_function(
#     get_items_from_db,
#     caller=assistant,
#     executor=user_proxy,
#     name="get_items_from_db",
#     description="Retrieve item details from the database. If an item_id is provided, it returns a single item; otherwise, it returns all items."
# )

#--------------------------processiong messages and checking for function calls----------------------------

async def process_messages():   
    global chat_status
    while chat_status == 'Chat ongoing':
        if not user_queue.empty():
            user_message = user_queue.get()
            print(f"Processing user message: {user_message}")
            
            chat_session.add_message("user", user_message)
            
            try:
                reply = await assistant.a_generate_reply(messages=chat_session.get_messages(), sender=user_proxy)
                
                if isinstance(reply, str):
                    chat_session.add_message("assistant", reply)
                    print_queue.put({'user': assistant.name, 'message': reply})
                elif isinstance(reply, dict) and 'tool_calls' in reply:
                    for tool_call in reply['tool_calls']:
                        if tool_call['type'] == 'function':
                            function_name = tool_call['function']['name']
                            function_args = json.loads(tool_call['function']['arguments'])
                            
                            try:
                                if function_name == 'save_item_to_db':
                                    result = save_item_to_db(function_args)
                                    if "successfully" in result:
                                        # Send a refresh message to the frontend
                                        print_queue.put({
                                            'user': 'System',
                                            'message': 'refresh_table'  # Special message to trigger refresh
                                        })
                                elif function_name == 'get_items_from_db':
                                    result = get_items_from_db(**function_args)
                                else:
                                    raise ValueError(f"Unknown function: {function_name}")
                                
                                system_message = f"Function {function_name} executed. Result: {result}"
                                chat_session.add_message("system", system_message)
                                print_queue.put({'user': "System", 'message': system_message})
                                
                                new_reply = await assistant.a_generate_reply(messages=chat_session.get_messages(), sender=user_proxy)
                                chat_session.add_message("assistant", new_reply)
                                print_queue.put({'user': assistant.name, 'message': new_reply})
                            except Exception as e:
                                error_message = f"Error executing function {function_name}: {str(e)}"
                                chat_session.add_message("system", error_message)
                                print_queue.put({'user': "System", 'message': error_message})
            
            except Exception as e:
                error_message = f"Error generating reply: {str(e)}"
                print(error_message)
                chat_session.add_message("system", error_message)
                print_queue.put({'user': "System", 'message': error_message})
                
                error_reply = await assistant.a_generate_reply(messages=chat_session.get_messages(), sender=user_proxy)
                chat_session.add_message("assistant", error_reply)
                print_queue.put({'user': assistant.name, 'message': error_reply})
        
        await asyncio.sleep(0.1)

def run_chat(initial_message: str) -> None:
    global chat_status, chat_session
    chat_session = ChatSession()
    try:
        chat_status = 'Chat ongoing'
        print(f"Starting chat with message: {initial_message}")
        
        chat_session.add_message("system", assistant.system_message)
        chat_session.add_message("user", initial_message)
        user_queue.put(initial_message)
        asyncio.run(process_messages())
        
        print("Chat ended")
        chat_status = "ended"
    except Exception as e:
        chat_status = "error"
        error_message = f"An error occurred in run_chat: {str(e)}"
        print(error_message)
        print_queue.put({'user': "System", 'message': error_message})


#--------------------------api routs----------------------------       

@app.route('/api/start_chat', methods=['POST', 'OPTIONS'])
def start_chat():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    elif request.method == 'POST':
        global chat_status
        try:
            if chat_status == 'error':
                chat_status = 'ended'
            with print_queue.mutex:
                print_queue.queue.clear()
            with user_queue.mutex:
                user_queue.queue.clear()
            initial_message = request.json.get('message', "I want to add a new item.")
            print(f"Starting new chat with initial message: {initial_message}")
            thread = threading.Thread(
                target=run_chat, 
                args=(initial_message,)
            )
            thread.start()
            return jsonify({'status': 'Chat started'})
        except Exception as e:
            print(f"Error starting chat: {str(e)}")
            return jsonify({'status': 'Error occurred', 'error': str(e)})

@app.route('/api/send_message', methods=['POST'])
def send_message():
    user_input = request.json['message']
    print(f"Received message from user: {user_input}")
    user_queue.put(user_input)
    return jsonify({'status': 'Message Received'})

@app.route('/api/get_message', methods=['GET'])
def get_messages():
    global chat_status 
    if not print_queue.empty():
        msg = print_queue.get()
        print(f"Sending message to frontend: {msg}")
        return jsonify({'message': msg, 'chat_status': chat_status}), 200
    else:
        print(f"No message to send. Current chat status: {chat_status}")
        return jsonify({'message': None, 'chat_status': chat_status}), 200
    
    
@app.route('/api/get_items', methods=['GET'])
def get_items():
    try:
        # Get DataTables parameters
        draw = request.args.get('draw', type=int, default=1)
        
        # Get items from database
        items = get_items_from_db()
        
        # Prepare response in DataTables format
        response = {
            'draw': draw,
            'recordsTotal': len(items),
            'recordsFiltered': len(items),
            'data': items
        }
        
        print("Sending data to DataTable:", response)  # Debug print
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in get_items API: {str(e)}")  # Debug print
        return jsonify({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e)
        }), 500

@app.route('/api/delete_item/<item_code>', methods=['DELETE'])
def delete_item(item_code):
    try:
        success = delete_item_from_db(item_code)
        if success:
            return jsonify({'message': 'Item deleted successfully'})
        return jsonify({'error': 'Failed to delete item'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update_item/<item_code>', methods=['PUT'])
def update_item(item_code):
    try:
        item_data = request.json
        success = update_item_in_db(item_code, item_data)
        if success:
            return jsonify({'message': 'Item updated successfully'})
        return jsonify({'error': 'Failed to update item'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5008, debug=True)