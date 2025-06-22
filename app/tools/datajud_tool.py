"""
DataJud API Tool for LangChain Agent.

This module provides a LangChain tool for interacting with the DataJud API
to fetch legal case information including process status, movements, and hearing schedules.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, validator
import re

from app.config import settings

# Configure logger
logger = logging.getLogger(__name__)


class CNJFormatError(Exception):
    """Exception raised when a CNJ number format is invalid."""
    pass


class DataJudAPIError(Exception):
    """Exception raised when an error occurs while interacting with DataJud API."""
    pass


class ProcessQuery(BaseModel):
    """
    Model for process query parameters.
    """
    cnj_number: str = Field(
        ..., 
        description="CNJ formatted process number (NNNNNNN-DD.YYYY.J.TR.OOOO)"
    )
    
    @validator("cnj_number")
    def validate_cnj_number(cls, v):
        """Validate CNJ number format."""
        pattern = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
        if not re.match(pattern, v):
            raise ValueError(
                "Invalid CNJ number format. Expected: NNNNNNN-DD.YYYY.J.TR.OOOO"
            )
        return v


class MovementsQuery(ProcessQuery):
    """
    Model for movements query parameters.
    """
    limit: int = Field(
        default=10,
        description="Maximum number of movements to return"
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Start date for movements (YYYY-MM-DD)"
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date for movements (YYYY-MM-DD)"
    )
    
    @validator("limit")
    def validate_limit(cls, v):
        """Validate limit is positive and not too large."""
        if v < 1:
            raise ValueError("Limit must be positive")
        if v > 100:
            raise ValueError("Limit cannot exceed 100")
        return v
    
    @validator("start_date", "end_date")
    def validate_date_format(cls, v):
        """Validate date format."""
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        return v


class DataJudTool(BaseTool):
    """
    Tool for interacting with the DataJud API.
    
    This tool allows the agent to fetch legal case information from the
    DataJud API, including process status, movements, and hearing schedules.
    """
    name = "datajud_tool"
    description = """
    Use this tool to fetch information about legal cases from the DataJud API.
    
    This tool can:
    1. Get the current status of a process
    2. Get recent movements (updates) of a process
    3. Get scheduled hearings for a process
    4. Get detailed information about a process
    
    Input should be a JSON string with the following format:
    {
        "operation": "get_process_status" | "get_process_movements" | "get_process_hearings" | "get_process_details",
        "cnj_number": "NNNNNNN-DD.YYYY.J.TR.OOOO",
        "limit": 10,  # Optional, for movements
        "start_date": "YYYY-MM-DD",  # Optional, for movements
        "end_date": "YYYY-MM-DD"  # Optional, for movements
    }
    """
    
    def __init__(self):
        """Initialize the DataJud tool with API configuration."""
        super().__init__()
        self.api_base_url = settings.DATAJUD_API_BASE_URL
        self.api_key = settings.DATAJUD_API_KEY
        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    async def _arun(self, query: str) -> str:
        """
        Asynchronously run the tool with the given query.
        
        Args:
            query: JSON string with query parameters
            
        Returns:
            JSON string with the API response
            
        Raises:
            Exception: If the query is invalid or the API request fails
        """
        try:
            # Parse the query
            query_dict = json.loads(query)
            operation = query_dict.get("operation")
            
            # Validate operation
            if operation not in [
                "get_process_status",
                "get_process_movements",
                "get_process_hearings",
                "get_process_details"
            ]:
                return json.dumps({
                    "error": f"Invalid operation: {operation}",
                    "valid_operations": [
                        "get_process_status",
                        "get_process_movements",
                        "get_process_hearings",
                        "get_process_details"
                    ]
                })
            
            # Call the appropriate method based on the operation
            if operation == "get_process_status":
                process_query = ProcessQuery(cnj_number=query_dict["cnj_number"])
                result = await self._get_process_status(process_query.cnj_number)
                
            elif operation == "get_process_movements":
                movements_query = MovementsQuery(
                    cnj_number=query_dict["cnj_number"],
                    limit=query_dict.get("limit", 10),
                    start_date=query_dict.get("start_date"),
                    end_date=query_dict.get("end_date")
                )
                result = await self._get_process_movements(
                    movements_query.cnj_number,
                    movements_query.limit,
                    movements_query.start_date,
                    movements_query.end_date
                )
                
            elif operation == "get_process_hearings":
                process_query = ProcessQuery(cnj_number=query_dict["cnj_number"])
                result = await self._get_process_hearings(process_query.cnj_number)
                
            elif operation == "get_process_details":
                process_query = ProcessQuery(cnj_number=query_dict["cnj_number"])
                result = await self._get_process_details(process_query.cnj_number)
            
            # Return the result as a JSON string
            return json.dumps(result, ensure_ascii=False, default=str)
            
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON query"})
        except ValueError as e:
            return json.dumps({"error": str(e)})
        except CNJFormatError as e:
            return json.dumps({"error": str(e)})
        except DataJudAPIError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            logger.exception(f"Unexpected error in DataJudTool: {e}")
            return json.dumps({"error": f"Unexpected error: {str(e)}"})
    
    def _run(self, query: str) -> str:
        """
        Run the tool with the given query (synchronous version).
        
        This method is required by the BaseTool interface but is not
        implemented for this async tool. It raises a NotImplementedError.
        
        Args:
            query: JSON string with query parameters
            
        Raises:
            NotImplementedError: Always raised as this tool is async-only
        """
        raise NotImplementedError("DataJudTool is async-only, use _arun instead")
    
    async def _get_process_status(self, cnj_number: str) -> Dict[str, Any]:
        """
        Get the current status of a process.
        
        Args:
            cnj_number: CNJ formatted process number
            
        Returns:
            Dictionary with process status information
            
        Raises:
            DataJudAPIError: If the API request fails
        """
        try:
            # Validate CNJ number format
            self._validate_cnj_format(cnj_number)
            
            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/processos/{cnj_number}/status",
                    headers=self.headers
                )
                
                # Check for errors
                if response.status_code != 200:
                    error_message = f"DataJud API error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise DataJudAPIError(error_message)
                
                # Parse response
                data = response.json()
                
                # Format the response for the agent
                return {
                    "cnj_number": cnj_number,
                    "status": data.get("status", "unknown"),
                    "last_update": data.get("dataAtualizacao"),
                    "court": data.get("tribunal"),
                    "instance": data.get("instancia"),
                    "secrecy_level": data.get("nivelSigilo", 0),
                    "raw_data": data
                }
                
        except httpx.HTTPError as e:
            error_message = f"HTTP error while fetching process status: {e}"
            logger.error(error_message)
            raise DataJudAPIError(error_message)
    
    async def _get_process_movements(
        self,
        cnj_number: str,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get recent movements (updates) of a process.
        
        Args:
            cnj_number: CNJ formatted process number
            limit: Maximum number of movements to return
            start_date: Start date for movements (YYYY-MM-DD)
            end_date: End date for movements (YYYY-MM-DD)
            
        Returns:
            Dictionary with process movements
            
        Raises:
            DataJudAPIError: If the API request fails
        """
        try:
            # Validate CNJ number format
            self._validate_cnj_format(cnj_number)
            
            # Prepare query parameters
            params = {"limit": limit}
            if start_date:
                params["dataInicio"] = start_date
            if end_date:
                params["dataFim"] = end_date
            
            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/processos/{cnj_number}/movimentacoes",
                    headers=self.headers,
                    params=params
                )
                
                # Check for errors
                if response.status_code != 200:
                    error_message = f"DataJud API error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise DataJudAPIError(error_message)
                
                # Parse response
                data = response.json()
                
                # Format the response for the agent
                movements = []
                for mov in data.get("movimentacoes", []):
                    movements.append({
                        "id": mov.get("id"),
                        "date": mov.get("data"),
                        "description": mov.get("descricao"),
                        "type": mov.get("tipo"),
                        "complementary_info": mov.get("complemento")
                    })
                
                return {
                    "cnj_number": cnj_number,
                    "total_movements": len(movements),
                    "movements": movements,
                    "raw_data": data
                }
                
        except httpx.HTTPError as e:
            error_message = f"HTTP error while fetching process movements: {e}"
            logger.error(error_message)
            raise DataJudAPIError(error_message)
    
    async def _get_process_hearings(self, cnj_number: str) -> Dict[str, Any]:
        """
        Get scheduled hearings for a process.
        
        Args:
            cnj_number: CNJ formatted process number
            
        Returns:
            Dictionary with process hearings
            
        Raises:
            DataJudAPIError: If the API request fails
        """
        try:
            # Validate CNJ number format
            self._validate_cnj_format(cnj_number)
            
            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/processos/{cnj_number}/audiencias",
                    headers=self.headers
                )
                
                # Check for errors
                if response.status_code != 200:
                    error_message = f"DataJud API error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise DataJudAPIError(error_message)
                
                # Parse response
                data = response.json()
                
                # Format the response for the agent
                hearings = []
                for hearing in data.get("audiencias", []):
                    hearings.append({
                        "id": hearing.get("id"),
                        "date": hearing.get("data"),
                        "time": hearing.get("hora"),
                        "type": hearing.get("tipo"),
                        "location": hearing.get("local"),
                        "status": hearing.get("status"),
                        "notes": hearing.get("observacoes")
                    })
                
                return {
                    "cnj_number": cnj_number,
                    "total_hearings": len(hearings),
                    "hearings": hearings,
                    "raw_data": data
                }
                
        except httpx.HTTPError as e:
            error_message = f"HTTP error while fetching process hearings: {e}"
            logger.error(error_message)
            raise DataJudAPIError(error_message)
    
    async def _get_process_details(self, cnj_number: str) -> Dict[str, Any]:
        """
        Get detailed information about a process.
        
        Args:
            cnj_number: CNJ formatted process number
            
        Returns:
            Dictionary with detailed process information
            
        Raises:
            DataJudAPIError: If the API request fails
        """
        try:
            # Validate CNJ number format
            self._validate_cnj_format(cnj_number)
            
            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/processos/{cnj_number}",
                    headers=self.headers
                )
                
                # Check for errors
                if response.status_code != 200:
                    error_message = f"DataJud API error: {response.status_code} - {response.text}"
                    logger.error(error_message)
                    raise DataJudAPIError(error_message)
                
                # Parse response
                data = response.json()
                
                # Format the response for the agent
                # Extract and format parties information
                parties = []
                for party in data.get("partes", []):
                    parties.append({
                        "name": party.get("nome"),
                        "role": party.get("papel"),
                        "document": party.get("documento"),
                        "type": party.get("tipo")
                    })
                
                # Extract and format subject information
                subjects = []
                for subject in data.get("assuntos", []):
                    subjects.append({
                        "code": subject.get("codigo"),
                        "description": subject.get("descricao")
                    })
                
                return {
                    "cnj_number": cnj_number,
                    "court": data.get("tribunal"),
                    "instance": data.get("instancia"),
                    "jurisdiction": data.get("comarca"),
                    "class": {
                        "code": data.get("classe", {}).get("codigo"),
                        "description": data.get("classe", {}).get("descricao")
                    },
                    "filing_date": data.get("dataDistribuicao"),
                    "judge": data.get("juiz"),
                    "value": data.get("valorCausa"),
                    "subjects": subjects,
                    "parties": parties,
                    "status": data.get("status"),
                    "secrecy_level": data.get("nivelSigilo", 0),
                    "priority": data.get("prioridade", False),
                    "electronic": data.get("eletronico", True),
                    "raw_data": data
                }
                
        except httpx.HTTPError as e:
            error_message = f"HTTP error while fetching process details: {e}"
            logger.error(error_message)
            raise DataJudAPIError(error_message)
    
    def _validate_cnj_format(self, cnj_number: str) -> None:
        """
        Validate CNJ number format.
        
        Args:
            cnj_number: CNJ formatted process number
            
        Raises:
            CNJFormatError: If the CNJ number format is invalid
        """
        pattern = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
        if not re.match(pattern, cnj_number):
            error_message = f"Invalid CNJ number format: {cnj_number}. Expected: NNNNNNN-DD.YYYY.J.TR.OOOO"
            logger.error(error_message)
            raise CNJFormatError(error_message)
