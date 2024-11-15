# AutoGen Dynamic Chat Integration

![UI Screenshot](images/screen.png)

This project demonstrates how AutoGen agents can be used to dynamically execute functions through a discussion where it can be easily integrate with existing systems.

## Project Overview

This application showcases the integration of AutoGen's AI agents with a Flask-based web API and a SQL Server database. It demonstrates how AI agents can:

1. Engage in dynamic conversations with users
2. Interpret user intents
3. Execute database operations based on the conversation

## Current Features
- 🤖 Dynamic AI-driven chat interface
- 📊 Real-time inventory management with DataTables
- 🔄 Automatic refresh after operations
- 💾 CRUD operations through both chat and UI
- 🔍 Advanced search and filtering capabilities

## Key Components

- **AutoGen Agents**: 
  - `AssistantAgent`: Interprets user requests and manages the conversation flow
  - `UserProxyAgent`: Executes functions as directed by the AssistantAgent

- **Flask API**: Provides endpoints for starting chats, sending messages, and retrieving responses

- **Database Integration**: Uses pyodbc to connect to a SQL Server database for CRUD operations on inventory items

## Features

1. **Dynamic Function Execution**: The AI can decide which function to call based on the conversation context.
2. **Database Operations**: 
   - Add new items to the inventory
   - Retrieve item information  
3. **Conversational UI**: Users interact with the system through natural language.
4. **Asynchronous Processing**: Utilizes asyncio for non-blocking operations.

## Setup and Installation

1. Clone the repository
```bash
git clone https://github.com/ranga-tec/Autogen-dynamic-functions.git
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure your database connection in `app.py`

4. Run the application
```bash
python app.py
```

## Future Enhancements

- This approach is very useful when it comes to voice control systems or for integrating voice control for existing systems.
- Easily can be extended to enhance advanced autogen AI capabilities to systems.

## Credits
UI influenced by [Yeyu Huang's work](https://substack.com/@yeyuhuang)