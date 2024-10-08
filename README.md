
![ui](images/image.png "Autogen Dynamic Function ui")


# AutoGen Dynamic Chat Integration

This project demonstrates how AutoGen agents can be used to dynamically execute functions through a discussion where it can be easily integrate with existing systems.

## Project Overview

This application showcases the integration of AutoGen's AI agents with a Flask-based web API and a SQL Server database. It demonstrates how AI agents can:

1. Engage in dynamic conversations with users
2. Interpret user intents
3. Execute database operations based on the conversation


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

## Future Enhancements

- This aproach is very use full when it comes to voice control systems or for imtergrate voice control for exisiting systems.
- Easily can be extended to enhance advance autogen AI capabilities to systems.

Do you want me to build an fucomplete inventory management system ? 


