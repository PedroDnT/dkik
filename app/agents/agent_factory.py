"""
LangChain Agent Factory for the DKIK WhatsApp Bot.

This module provides a factory function to create LangChain agents
with appropriate configuration for the DKIK WhatsApp Bot, including
tools, prompts, and memory for legal case tracking in TJSP.
"""
import logging
from typing import Any, Dict, List, Optional

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import BaseTool
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.tools import get_tools

# Configure logger
logger = logging.getLogger(__name__)


# System prompts for different languages
SYSTEM_PROMPTS = {
    "pt-BR": """
    Você é DKIK, um assistente jurídico especializado em acompanhamento de processos no Tribunal de Justiça de São Paulo (TJSP).

    Suas principais funções são:
    1. Consultar o status atual de processos jurídicos usando o número CNJ (formato NNNNNNN-DD.YYYY.J.TR.OOOO)
    2. Verificar movimentações recentes de processos
    3. Informar sobre audiências agendadas
    4. Permitir que usuários acompanhem processos e recebam notificações automáticas

    Diretrizes importantes:
    - Sempre responda em português claro e conciso
    - Quando o usuário fornecer um número de processo, verifique se está no formato CNJ correto (NNNNNNN-DD.YYYY.J.TR.OOOO)
    - Se o usuário quiser acompanhar um processo, explique como funciona o sistema de notificações
    - Seja educado e profissional, usando linguagem apropriada para advogados
    - Quando não souber a resposta, seja honesto e sugira alternativas
    - Não forneça conselhos jurídicos substantivos ou opiniões sobre casos
    - Mantenha as respostas concisas e adequadas para mensagens de WhatsApp

    Você tem acesso às seguintes ferramentas:
    - datajud_tool: Para consultar informações sobre processos no DataJud
    - process_tool: Para gerenciar processos no banco de dados
    - notification_tool: Para enviar notificações aos usuários
    - subscription_tool: Para gerenciar assinaturas de processos
    - user_tool: Para gerenciar informações de usuários

    Use essas ferramentas quando necessário para fornecer informações precisas e atualizadas sobre processos jurídicos.
    """,
    
    "en-US": """
    You are DKIK, a legal assistant specialized in tracking cases in the São Paulo State Court (TJSP).

    Your main functions are:
    1. Check the current status of legal cases using the CNJ number (format NNNNNNN-DD.YYYY.J.TR.OOOO)
    2. Verify recent case movements
    3. Inform about scheduled hearings
    4. Allow users to track cases and receive automatic notifications

    Important guidelines:
    - Always respond in clear and concise language
    - When the user provides a case number, check if it's in the correct CNJ format (NNNNNNN-DD.YYYY.J.TR.OOOO)
    - If the user wants to track a case, explain how the notification system works
    - Be polite and professional, using appropriate language for lawyers
    - When you don't know the answer, be honest and suggest alternatives
    - Don't provide substantive legal advice or opinions on cases
    - Keep responses concise and suitable for WhatsApp messages

    You have access to the following tools:
    - datajud_tool: To query information about cases in DataJud
    - process_tool: To manage processes in the database
    - notification_tool: To send notifications to users
    - subscription_tool: To manage case subscriptions
    - user_tool: To manage user information

    Use these tools when necessary to provide accurate and up-to-date information about legal cases.
    """
}


async def create_agent(
    tools: List[BaseTool],
    user_id: str,
    user_name: Optional[str] = None,
    user_language: str = "pt-BR",
) -> AgentExecutor:
    """
    Create a LangChain agent for the DKIK WhatsApp Bot.
    
    This function creates an agent with the specified tools, memory,
    and configuration for the DKIK WhatsApp Bot.
    
    Args:
        tools: List of LangChain tools to make available to the agent
        user_id: User ID for personalized interactions
        user_name: Optional user name for personalized greeting
        user_language: User's preferred language (defaults to Portuguese)
        
    Returns:
        Configured AgentExecutor
    """
    try:
        # Get the appropriate system prompt based on language
        system_prompt = SYSTEM_PROMPTS.get(user_language, SYSTEM_PROMPTS["pt-BR"])
        
        # Add personalization if user name is provided
        if user_name:
            greeting = "Olá, " if user_language == "pt-BR" else "Hello, "
            system_prompt = f"{system_prompt}\n\nO nome do usuário atual é {user_name}."
        
        # Create memory for conversation context
        memory = ConversationBufferMemory(
            return_messages=True,
            memory_key="chat_history",
            input_key="input",
            output_key="output"
        )
        
        # Create the prompt template
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create the language model
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.3,  # Lower temperature for more consistent responses
            api_key=settings.OPENAI_API_KEY,
        )
        
        # Create the agent
        agent = create_openai_functions_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
        
        # Create the agent executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=memory,
            verbose=settings.DEBUG,
            handle_parsing_errors=True,
            max_iterations=3,  # Limit iterations to avoid excessive API calls
            return_intermediate_steps=False,  # Don't return intermediate steps to save tokens
        )
        
        logger.info(f"Created agent for user {user_id} with {len(tools)} tools")
        return agent_executor
        
    except Exception as e:
        logger.exception(f"Error creating agent: {e}")
        raise


def get_cnj_from_text(text: str) -> Optional[str]:
    """
    Extract a CNJ number from text if present.
    
    Args:
        text: Text to search for CNJ number
        
    Returns:
        CNJ number if found, None otherwise
    """
    import re
    
    # CNJ format: NNNNNNN-DD.YYYY.J.TR.OOOO
    pattern = r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}"
    match = re.search(pattern, text)
    
    if match:
        return match.group(0)
    
    return None


def extract_legal_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract legal entities from text.
    
    This function extracts common legal entities from text, such as
    case numbers, court names, and legal terms.
    
    Args:
        text: Text to extract entities from
        
    Returns:
        Dictionary of entity types and values
    """
    entities = {
        "cnj_numbers": [],
        "courts": [],
        "legal_terms": [],
    }
    
    # Extract CNJ numbers
    cnj_number = get_cnj_from_text(text)
    if cnj_number:
        entities["cnj_numbers"].append(cnj_number)
    
    # Extract courts (simplified implementation)
    court_patterns = [
        "TJSP", "Tribunal de Justiça", "Fórum", "Vara", "Juizado"
    ]
    for pattern in court_patterns:
        if pattern.lower() in text.lower():
            entities["courts"].append(pattern)
    
    # Extract legal terms (simplified implementation)
    legal_terms = [
        "audiência", "sentença", "decisão", "despacho", "petição",
        "recurso", "agravo", "embargos", "liminar", "tutela"
    ]
    for term in legal_terms:
        if term.lower() in text.lower():
            entities["legal_terms"].append(term)
    
    return entities
