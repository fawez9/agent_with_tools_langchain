import os
import uuid
from dotenv import load_dotenv
from langchain.tools import tool
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from custom_prompt import get_custom_prompt

# Load environment variables
load_dotenv()

# Configure the Google GenAI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Define the mathematical functions
@tool
def add(a: float, b: float) -> float:
    """Adds two numbers"""
    return a + b

@tool
def subtract(a: float, b: float) -> float:
    """Subtracts the second number from the first"""
    return a - b

@tool
def multiply(a: float, b: float) -> float:
    """Multiplies two numbers"""
    return a * b

@tool
def divide(a: float, b: float) -> float:
    """Divides the first number by the second"""
    if b == 0:
        return "Error: Division by zero"
    return a / b

tools = [add, subtract, multiply, divide]
tool_names = [tool.name for tool in tools]
# Define the custom prompt
custom_prompt = get_custom_prompt()

# Define the prompt
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", custom_prompt),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# Initialize the LLM
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

# Define the chat history
class EnhancedChatMessageHistory(ChatMessageHistory):
    def get_last_result(self):
        for message in reversed(self.messages):
            if isinstance(message, AIMessage) and message.content.startswith("Result:"):
                return message.content.split("Result:", 1)[1].split(".", 1)[0].strip()
        return None
# Use a single session ID for now
session_id = str(uuid.uuid4())

# Initialize the chat history
memory = EnhancedChatMessageHistory(session_id=session_id)

# Create the agent
agent = create_tool_calling_agent(llm, tools, prompt)

# Create the AgentExecutor
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Create the agent with chat history
agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    lambda session_id: memory,
    input_messages_key="input",
    history_messages_key="chat_history",
)

calculation_cache = {}
previous_result = None

while True:
    user_input = input("Enter a math problem or press q to quit: ").strip()
    if user_input.lower() == 'q':
        break

    # Handle operator-prefixed inputs
    if user_input[0] in ['+', '-', '*', '/'] and previous_result is not None:
        user_input = f"{previous_result}{user_input}"

    # Update chat history
    memory.add_message(HumanMessage(content=user_input))

    try:
        result = agent_with_chat_history.invoke({
            "input": user_input,
            "tools": tools,
            "tool_names": tool_names,
            "chat_history": memory.messages,
            "previous_result": previous_result,
            "calculation_cache": calculation_cache
        }, config={"configurable": {"session_id": session_id}})

        # Extract the final answer
        if 'Final Answer:' in result['output']:
            final_answer = result['output'].split("Final Answer:")[-1].strip()
        else:
            final_answer = result['output'].strip()

        # Update the cache and previous_result
        if '=' in final_answer:
            expression, value = final_answer.split('=')
            calculation_cache[expression.strip()] = value.strip()
            previous_result = float(value.strip())

        # Update chat history with the agent's response
        memory.add_message(AIMessage(content=final_answer))
        print("Result: " + final_answer)
    except Exception as e:
        print(f"An error occurred: {str(e)}")