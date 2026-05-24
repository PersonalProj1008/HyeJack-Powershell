import time
import requests
from typing import List,Dict,Any,Optional
import os
import uuid
import json
import uuid
import argparse
import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.box import ROUNDED
import emoji
import time
import sys
import threading
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.align import Align
from rich.box import DOUBLE, ROUNDED, HEAVY
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from pathlib import Path
import psycopg2
from psycopg2 import sql, extras
import inquirer 
from typing import Optional, Dict, Tuple
import os
import tomli
from datetime import datetime
from InquirerPy import inquirer as inquirerPY
from InquirerPy.base.control import Choice

console = Console()

class GrokKnowledgeBaseFileManager:
    @staticmethod
    def get_files_with_write_time(filepaths: List[str]) -> List[Dict]:
        result = []
        
        for path in filepaths:
            if os.path.exists(path):
                result.append({
                    "path_name": path,
                    "last_write_time": os.path.getmtime(path)
                })
        
        return result
    @staticmethod
    def compare_file_states(old_list_str: str, new_list: List[Dict]):
        new_files_to_be_uploaded = []
        old_list:List=[]
        if not old_list_str:
            old_list_str="[]"
        if ((old_list_str.strip()) or (old_list_str!=None) ):
            old_list=json.loads(old_list_str)
        # Convert old list to dict for fast lookup
        old_map = {item["path_name"]: item["last_write_time"] for item in old_list}
        
        # This will become the updated master list
        total_upload_map = old_map.copy()
        
        for item in new_list:
            path = item["path_name"]
            new_time = item["last_write_time"]
            
            # Case 1: New file
            if path not in old_map:
                new_files_to_be_uploaded.append(item["path_name"])
                total_upload_map[path] = new_time
            
            # Case 2: Modified file
            elif new_time > old_map[path]:
                new_files_to_be_uploaded.append(item["path_name"])
                total_upload_map[path] = new_time
        
        # Convert total_upload_map back to list format
        total_upload_till_now = [
            {"path_name": path, "last_write_time": time}
            for path, time in total_upload_map.items()
        ]
        
        return {
            "new_files_to_be_uploaded": new_files_to_be_uploaded,
            "knowledge_base_total_upload_till_now_str": json.dumps(total_upload_till_now)
        }    
    
    @staticmethod
    def read_toml_file(file_path: str) -> dict:
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"TOML file not found: {file_path}")
        
        with open(path, "rb") as f:
            data = tomli.load(f)
        
        return data
    
class ALL_SQL_INTERACTIONS:
    # Topics table queries
    CREATE_NEW_TOPICS_ADD_COLLECTION_NAME = sql.SQL("INSERT INTO Topics (TOPIC, COLLECTION_NAME, COLLECTION_ID, KNOWLEDGE_BASE_FILES) VALUES (%s, %s, %s, %s) RETURNING ID")
    GET_ALL_TOPICS = sql.SQL("SELECT * FROM Topics ORDER BY ID")
    GET_TOPIC_BY_ID = sql.SQL("SELECT * FROM Topics WHERE ID = %s")
    GET_TOPIC_BY_NAME = sql.SQL("SELECT * FROM Topics WHERE TOPIC = %s")
    UPDATE_TOPIC = sql.SQL("UPDATE Topics SET TOPIC = %s, COLLECTION_NAME = %s, COLLECTION_ID = %s, KNOWLEDGE_BASE_FILES = %s WHERE ID = %s")
    DELETE_TOPIC = sql.SQL("DELETE FROM Topics WHERE ID = %s")
    UPDATE_TOPIC_COLLECTION = sql.SQL("UPDATE Topics SET COLLECTION_NAME = %s, COLLECTION_ID = %s WHERE ID = %s")
    UPDATE_TOPIC_KNOWLEDGE_BASE = sql.SQL("UPDATE Topics SET KNOWLEDGE_BASE_FILES = %s WHERE ID = %s")
    UPDATE_TOPIC_NAME_KNOWLEDGE_BASE = sql.SQL("UPDATE Topics SET KNOWLEDGE_BASE_FILES = %s WHERE TOPIC = %s")
    
    # Conversations table queries
    INSERT_CONVERSATION = sql.SQL("INSERT INTO Conversations (Topic_Name, Content, Is_User, Is_Bot, DateTime) VALUES (%s, %s, %s, %s, %s)")
    GET_CONVERSATIONS_BY_TOPIC = sql.SQL("SELECT * FROM Conversations WHERE Topic_Name = %s ORDER BY DateTime ASC")
    GET_CONVERSATIONS_BY_TOPIC_LIMITED = sql.SQL("SELECT * FROM Conversations WHERE Topic_Name = %s ORDER BY DateTime DESC LIMIT %s")
    GET_ALL_CONVERSATIONS = sql.SQL("SELECT * FROM Conversations ORDER BY DateTime DESC")
    DELETE_CONVERSATIONS_BY_TOPIC = sql.SQL("DELETE FROM Conversations WHERE Topic_Name = %s")
    DELETE_CONVERSATION_BY_ID = sql.SQL("DELETE FROM Conversations WHERE id = %s")
    GET_CONVERSATION_HISTORY = sql.SQL("SELECT * FROM Conversations WHERE Topic_Name = %s AND DateTime >= %s ORDER BY DateTime ASC")
    CLEAR_CONVERSATIONS = sql.SQL("DELETE FROM Conversations")
    
    # Current Topic table queries
    SET_CURRENT_TOPIC = sql.SQL("INSERT INTO CURRENT_TOPIC (ID, TOPIC_NAME) VALUES (1, %s) ON CONFLICT (ID) DO UPDATE SET TOPIC_NAME = EXCLUDED.TOPIC_NAME")
    GET_CURRENT_TOPIC = sql.SQL("SELECT TOPIC_NAME FROM CURRENT_TOPIC WHERE ID = 1")
    CLEAR_CURRENT_TOPIC = sql.SQL("DELETE FROM CURRENT_TOPIC WHERE ID = 1")
    
    # Credentials table queries
    INSERT_CREDENTIALS = sql.SQL("INSERT INTO Credentials (NEW_CREDENTIAL_PAIR, GROK_API_KEY, GROK_MANAGEMENT_KEY) VALUES (%s, %s, %s) RETURNING ID")
    GET_CREDENTIALS = sql.SQL("SELECT * FROM Credentials ORDER BY ID DESC LIMIT 1")
    UPDATE_CREDENTIALS = sql.SQL("UPDATE Credentials SET NEW_CREDENTIAL_PAIR = %s, GROK_API_KEY = %s, GROK_MANAGEMENT_KEY = %s WHERE ID = %s")
    DELETE_CREDENTIALS = sql.SQL("DELETE FROM Credentials WHERE ID = %s")
    GET_ALL_CREDENTIALS = sql.SQL("SELECT * FROM Credentials ORDER BY ID DESC")
    
    def __init__(self, host: str = None, database: str = None, user: str = None, password: str = None, port: int = 5432):
        """
        Initialize database connection parameters
        
        Args:
            host: PostgreSQL host
            database: Database name
            user: Database user
            password: Database password
            port: PostgreSQL port (default: 5432)
        """
        # Use default values if not provided
        self.connection_params = {
            'host': host or "postgres_db",
            'database': database or "poweragent_kb",
            'user': user or "poweradmin",
            'password': password or "StaticPassword123!",
            'port': port
        }
        self._connection = None
    
    def _get_connection(self):
        """Get database connection (creates new if none exists)"""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(**self.connection_params)
            self._connection.autocommit = False
        return self._connection
    
    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None
    
    def _execute_query(self, query: sql.SQL, params: tuple = None, fetch: bool = False):
        """
        Execute a database query
        
        Args:
            query: SQL query
            params: Query parameters
            fetch: Whether to fetch results
        
        Returns:
            Fetched results if fetch=True, else None
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cursor:
                cursor.execute(query, params)
                if fetch:
                    result = cursor.fetchall()
                else:
                    conn.commit()
                    result = None
                return result
        except Exception as e:
            conn.rollback()
            raise e
    
    def init_db(self):
        """Initialize database tables if they don't exist"""
        query = """
        CREATE TABLE IF NOT EXISTS Topics (
            ID SERIAL PRIMARY KEY,
            TOPIC TEXT NOT NULL,
            COLLECTION_NAME TEXT NOT NULL,
            COLLECTION_ID TEXT NULL,
            KNOWLEDGE_BASE_FILES TEXT NULL
        );
        
        CREATE TABLE IF NOT EXISTS Conversations (
            id SERIAL PRIMARY KEY,
            Topic_Name TEXT,
            DateTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            Content TEXT,
            Is_User BOOLEAN,
            Is_Bot BOOLEAN
        );
        
        CREATE TABLE IF NOT EXISTS CURRENT_TOPIC (
            ID SERIAL PRIMARY KEY,
            TOPIC_NAME TEXT NOT NULL,
            CONSTRAINT single_active_topic CHECK (ID = 1)
        );
        
        CREATE TABLE IF NOT EXISTS Credentials (
            ID SERIAL PRIMARY KEY,
            NEW_CREDENTIAL_PAIR TEXT NULL,
            GROK_API_KEY TEXT NULL,
            GROK_MANAGEMENT_KEY TEXT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_conversations_topic_name ON Conversations(Topic_Name);
        CREATE INDEX IF NOT EXISTS idx_conversations_datetime ON Conversations(DateTime);
        CREATE INDEX IF NOT EXISTS idx_topics_topic ON Topics(TOPIC);
        CREATE INDEX IF NOT EXISTS idx_current_topic_name ON CURRENT_TOPIC(TOPIC_NAME);
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query)
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
    
    # ==================== TOPICS FUNCTIONS ====================
    
    def create_topic(self, topic: str, collection_name: str = None, collection_id: str = None, knowledge_base_files: str = None) -> Optional[int]:
        """Create a new topic"""
        # If collection_name and collection_id are not provided, generate them

        
        query = self.CREATE_NEW_TOPICS_ADD_COLLECTION_NAME
        params = (topic, collection_name, collection_id, knowledge_base_files)
        result = self._execute_query(query, params, fetch=True)
        return result[0]['id'] if result else None
    
    def get_all_topics(self) -> List[Dict[str, Any]]:
        """Get all topics"""
        query = self.GET_ALL_TOPICS
        results = self._execute_query(query, fetch=True)
        return [dict(row) for row in results] if results else []
    
    def get_topic_by_id(self, topic_id: int) -> Optional[Dict[str, Any]]:
        """Get topic by ID"""
        query = self.GET_TOPIC_BY_ID
        params = (topic_id,)
        results = self._execute_query(query, params, fetch=True)
        return dict(results[0]) if results and len(results) > 0 else None
    
    def get_topic_by_name(self, topic_name: str) -> Dict[str, Any]:
        """Get topic by name"""
        query = self.GET_TOPIC_BY_NAME
        params = (topic_name,)
        results = self._execute_query(query, params, fetch=True)
        return dict(results[0]) if results and len(results) > 0 else {}
    
    def update_topic(self, topic_id: int, topic: str, collection_name: str, collection_id: str, knowledge_base_files: str) -> bool:
        """Update a topic"""
        query = self.UPDATE_TOPIC
        params = (topic, collection_name, collection_id, knowledge_base_files, topic_id)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def delete_topic(self, topic_id: int) -> bool:
        """Delete a topic and its conversations"""
        try:
            # First get the topic to get the name for conversation deletion
            topic = self.get_topic_by_id(topic_id)
            if topic:
                # Delete conversations for this topic
                self.delete_conversations_by_topic(topic['topic'])
            # Delete the topic
            query = self.DELETE_TOPIC
            params = (topic_id,)
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def update_topic_collection(self, topic_id: int, collection_name: str, collection_id: str) -> bool:
        """Update only the collection information for a topic"""
        query = self.UPDATE_TOPIC_COLLECTION
        params = (collection_name, collection_id, topic_id)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def update_topic_knowledge_base(self, topic_id: int, knowledge_base_files: str) -> bool:
        """Update only the knowledge base files for a topic"""
        query = self.UPDATE_TOPIC_KNOWLEDGE_BASE
        params = (knowledge_base_files, topic_id)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False

    def update_knowledge_base_by_topic_name(self, topic_name: str, knowledge_base_files: str) -> bool:
        """Update only the knowledge base files for a topic"""
        query = self.UPDATE_TOPIC_NAME_KNOWLEDGE_BASE
        params = (knowledge_base_files, topic_name)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    # ==================== CONVERSATIONS FUNCTIONS ====================
    
    def add_conversation(self, topic_name: str, content: str, is_user: bool = False, is_bot: bool = False, timestamp: datetime = None) -> bool:
        """Add a conversation entry"""
        if timestamp is None:
            timestamp = datetime.now()
        query = self.INSERT_CONVERSATION
        params = (topic_name, content, is_user, is_bot, timestamp)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def add_user_message(self, topic_name: str, content: str) -> bool:
        """Add a user message to conversation"""
        return self.add_conversation(topic_name, content, is_user=True, is_bot=False)
    
    def add_bot_message(self, topic_name: str, content: str) -> bool:
        """Add a bot message to conversation"""
        return self.add_conversation(topic_name, content, is_user=False, is_bot=True)
    
    def get_conversations_by_topic(self, topic_name: str, limit: int = None) -> List[Dict[str, Any]]:
        """Get conversations for a specific topic"""
        if limit:
            query = self.GET_CONVERSATIONS_BY_TOPIC_LIMITED
            params = (topic_name, limit)
            results = self._execute_query(query, params, fetch=True)
        else:
            query = self.GET_CONVERSATIONS_BY_TOPIC
            params = (topic_name,)
            results = self._execute_query(query, params, fetch=True)
        
        return [dict(row) for row in results] if results else []
    
    def get_all_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations"""
        query = self.GET_ALL_CONVERSATIONS
        results = self._execute_query(query, fetch=True)
        return [dict(row) for row in results] if results else []
    
    def delete_conversations_by_topic(self, topic_name: str) -> bool:
        """Delete all conversations for a topic"""
        query = self.DELETE_CONVERSATIONS_BY_TOPIC
        params = (topic_name,)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def delete_conversation_by_id(self, conversation_id: int) -> bool:
        """Delete a specific conversation by ID"""
        query = self.DELETE_CONVERSATION_BY_ID
        params = (conversation_id,)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def get_conversation_history(self, topic_name: str, since: datetime = None) -> List[Dict[str, Any]]:
        """Get conversation history since a specific time"""
        if since:
            query = self.GET_CONVERSATION_HISTORY
            params = (topic_name, since)
            results = self._execute_query(query, params, fetch=True)
        else:
            results = self.get_conversations_by_topic(topic_name)
        
        return [dict(row) for row in results] if results else []
    
    def clear_all_conversations(self) -> bool:
        """Clear all conversations (use with caution)"""
        query = self.CLEAR_CONVERSATIONS
        try:
            self._execute_query(query)
            return True
        except Exception:
            return False
    
    def get_history_topics(self) -> List[str]:
        """Get unique topic names from Topics table"""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT TOPIC FROM Topics ORDER BY TOPIC ASC;")
                topics = [row[0] for row in cursor.fetchall()]
                return topics
        except Exception:
            return []
    
    # ==================== CURRENT TOPIC FUNCTIONS ====================
    
    def set_current_topic(self, topic_name: str) -> bool:
        """Set the current active topic"""
        query = self.SET_CURRENT_TOPIC
        params = (topic_name,)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def get_current_topic(self) -> Optional[str]:
        """Get the current active topic name"""
        query = self.GET_CURRENT_TOPIC
        results = self._execute_query(query, fetch=True)
        return results[0]['topic_name'] if results and len(results) > 0 else None
    
    def clear_current_topic(self) -> bool:
        """Clear the current active topic"""
        query = self.CLEAR_CURRENT_TOPIC
        try:
            self._execute_query(query)
            return True
        except Exception:
            return False
    
    # ==================== CREDENTIALS FUNCTIONS ====================
    
    def add_credentials(self, new_credential_pair: str = None, grok_api_key: str = None, grok_management_key: str = None) -> Optional[int]:
        """Add new credentials"""
        query = self.INSERT_CREDENTIALS
        params = (new_credential_pair, grok_api_key, grok_management_key)
        result = self._execute_query(query, params, fetch=True)
        return result[0]['id'] if result else None
    
    def get_latest_credentials(self) -> Optional[Dict[str, Any]]:
        """Get the most recent credentials"""
        query = self.GET_CREDENTIALS
        results = self._execute_query(query, fetch=True)
        return dict(results[0]) if results and len(results) > 0 else None
    
    def update_credentials(self, cred_id: int, new_credential_pair: str = None, grok_api_key: str = None, grok_management_key: str = None) -> bool:
        """Update credentials by ID"""
        query = self.UPDATE_CREDENTIALS
        params = (new_credential_pair, grok_api_key, grok_management_key, cred_id)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def delete_credentials(self, cred_id: int) -> bool:
        """Delete credentials by ID"""
        query = self.DELETE_CREDENTIALS
        params = (cred_id,)
        try:
            self._execute_query(query, params)
            return True
        except Exception:
            return False
    
    def get_all_credentials(self) -> List[Dict[str, Any]]:
        """Get all credentials"""
        query = self.GET_ALL_CREDENTIALS
        results = self._execute_query(query, fetch=True)
        return [dict(row) for row in results] if results else []
    
    # ==================== DUMMY FUNCTIONS ====================
    
    def _derive_collection_from_topic(self, topic: str) -> Tuple[str, str]:
        """
        Dummy function to derive collection_name and collection_id from a topic
        This is a placeholder - replace with actual logic for your use case
        """
        # Clean the topic name to create a collection name
        collection_name = topic.lower().replace(' ', '_').replace('-', '_')
        # Add timestamp or unique identifier for uniqueness
        import hashlib
        import time
        unique_id = hashlib.md5(f"{topic}_{time.time()}".encode()).hexdigest()[:8]
        collection_id = f"coll_{collection_name}_{unique_id}"
        
        return collection_name, collection_id
    
    def update_knowledge_base_for_topic(self, topic_id: int, knowledge_base_paths: List[str]) -> bool:
        """
        Dummy function to update knowledge base files for a topic
        This is a placeholder - replace with actual logic for your use case
        """
        # Convert list of paths to a comma-separated string or JSON
        knowledge_base_str = ','.join(knowledge_base_paths)
        return self.update_topic_knowledge_base(topic_id, knowledge_base_str)

# ==================== INQUIRER CLI COMPONENT ====================
class CredentialManager:
    """Manager class for interacting with the Credentials table"""
    
    def __init__(self, host: str, database: str, user: str, password: str, port: int = 5432):
        """
        Initialize database connection parameters
        
        Args:
            host: PostgreSQL host
            database: Database name
            user: Database user
            password: Database password
            port: PostgreSQL port (default: 5432)
        """
        self.connection_params = {
            'host': host,
            'database': database,
            'user': user,
            'password': password,
            'port': port
        }
        self._connection = None
    
    def _get_connection(self):
        """Get database connection (creates new if none exists)"""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(**self.connection_params)
            self._connection.autocommit = False
        return self._connection
    
    def close(self):
        """Close database connection"""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None
    
    def _execute_query(self, query: sql.SQL, params: tuple = None, fetch: bool = False):
        """
        Execute a database query
        
        Args:
            query: SQL query
            params: Query parameters
            fetch: Whether to fetch results
        
        Returns:
            Fetched results if fetch=True, else None
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=extras.DictCursor) as cursor:
                cursor.execute(query, params)
                if fetch:
                    result = cursor.fetchall()
                else:
                    conn.commit()
                    result = None
                return result
        except Exception as e:
            conn.rollback()
            raise e
    
    def get_credential(self) -> Optional[Dict]:
        """
        Get the single credential record
        
        Returns:
            Dictionary with credential data or None if no record exists
        """
        query = sql.SQL("SELECT * FROM Credentials LIMIT 1")
        results = self._execute_query(query, fetch=True)
        
        if results and len(results) > 0:
            return dict(results[0])
        return None
    
    def create_initial_record(self):
        """
        Create initial credential record with NULL values if no record exists
        """
        query = sql.SQL("""
            INSERT INTO Credentials (GROK_API_KEY, GROK_MANAGEMENT_KEY)
            VALUES (%s, %s)
        """)
        self._execute_query(query, (None, None))
    
    def update_grok_api_key(self, api_key: str):
        """
        Update the Grok API key
        
        Args:
            api_key: New API key
        """
        query = sql.SQL("""
            UPDATE Credentials 
            SET GROK_API_KEY = %s 
            WHERE ID = (SELECT ID FROM Credentials LIMIT 1)
        """)
        self._execute_query(query, (api_key,))
    
    def update_grok_management_key(self, management_key: str):
        """
        Update the Grok Management key
        
        Args:
            management_key: New management key
        """
        query = sql.SQL("""
            UPDATE Credentials 
            SET GROK_MANAGEMENT_KEY = %s 
            WHERE ID = (SELECT ID FROM Credentials LIMIT 1)
        """)
        self._execute_query(query, (management_key,))
    
    
    def display_current_credentials(self):
        """
        Display current credentials status
        """
        cred = self.get_credential()
        if not cred:
            print("  No credential record found!")
            return
        
        print("\n" + "="*50)
        print(" CURRENT CREDENTIALS STATUS")
        print("="*50)
        print(f" Grok API Key: {'✓ Set' if cred['grok_api_key'] else ' Not Set'}")
        print(f" Grok Management Key: {'✓ Set' if cred['grok_management_key'] else ' Not Set'}")
        print("="*50 + "\n")

class TopicSelectorCLI:
    """Inquirer-based CLI for topic selection and management using InquirerPy"""
    
    def __init__(self, db_handler: ALL_SQL_INTERACTIONS):
        self.db = db_handler
    
    def get_chat_topic(self) -> str:
        """
        Interactive topic selection with InquirerPy (arrow-based navigation)
        Returns selected topic name
        """
        # Initialize database and ensure tables exist
        self.db.init_db()
        
        while True:
            console.clear()
            console.print(Panel("[bold white]SELECT TOPIC[/bold white]", 
                                subtitle="[gray]Use Arrows to Navigate[/gray]"))
            
            # Check if there's a current active topic
            current_topic = self.db.get_current_topic()
            
            # Prepare main menu choices
            main_choices = [
                Choice(value="1", name="1. Enter New Topic"),
                Choice(value="2", name="2. Choose Topic From History"),
            ]
            
            # Add option to check current topic if one exists
            if current_topic:
                main_choices.insert(0, Choice(value="current", name=f"✓ Current Topic: {current_topic}"))
                main_choices.append(Choice(value="clear", name="4. Deselect Current Topic"))
            
            main_choices.append(Choice(value="exit", name="3. Exit Program" if not current_topic else "5. Exit Program"))
            
            # Main Menu selection using Arrows
            choice = inquirerPY.select(
                message="Select an option:",
                choices=main_choices,
                pointer="▶",
            ).execute()
            
            if choice == "exit":
                sys.exit()
            
            if choice == "current":
                # Display current topic information
                topic_data = self.db.get_topic_by_name(current_topic)
                if topic_data:
                    console.print(Panel(
                        f"[bold green]Current Active Chat Topic:[/bold green] {current_topic}\n\n"
                        f"[bold]Collection Name:[/bold] {topic_data['collection_name']}\n"
                        f"[bold]Collection ID:[/bold] {topic_data['collection_id']}\n"
                        f"[bold]Knowledge Base Files:[/bold] {topic_data['knowledge_base_files'] or 'None'}",
                        title="Current Topic Details",
                        border_style="cyan"
                    ))
                    
                    # Ask if user wants to continue with this topic
                    confirm = inquirerPY.select(
                        message="Continue with this topic?",
                        choices=[
                            Choice(value="yes", name="Yes, continue"),
                            Choice(value="no", name="No, select different topic"),
                        ],
                        pointer="▶"
                    ).execute()
                    
                    if confirm == "yes":
                        return current_topic
                    else:
                        continue
                else:
                    console.print("[yellow]Current topic reference found but topic data missing. Clearing...[/yellow]")
                    self.db.clear_current_topic()
                    import time
                    time.sleep(1)
                    continue
            
            if choice == "clear":
                # Clear current topic
                self.db.clear_current_topic()
                console.print("[green]Current topic deselected...[/green]")
                import time
                time.sleep(1)
                continue
            
            if choice == "1":
                topic = inquirerPY.text(
                    message="Enter New Chat Topic (or type 'back'):", 
                    default="General Discussion"
                ).execute()
                
                if topic.lower() == 'back':
                    continue
                    
                # Check if topic exists in Topics table
                existing_topic = self.db.get_topic_by_name(topic)
                if existing_topic:
                    text = "[bold cyan]Topic Present : Selecting Existing Topic[/bold cyan]"
                    info_text = "[dim]This topic already exists in the system[/dim]"
                    
                    panel = Panel(
                        f"{text}\n\n{info_text}",
                        border_style="green",
                        title="Topic Exists",
                        expand=True,
                    )
                    console.print(panel)
                    
                    import time
                    time.sleep(2)
                    
                    # Set as current topic
                    self.db.set_current_topic(topic)
                    return topic
                else:
                    # Create new topic with auto-generated collection info
                    db_host = os.getenv('PG_HOST', 'localhost')
                    db_name = os.getenv('PG_DB', 'poweragent_kb')
                    db_user = os.getenv('PG_USER', 'poweradmin')
                    db_password = os.getenv('PG_PASSWORD', 'StaticPassword123!')
                    cred_manager = CredentialManager(
                                host=db_host,
                                database=db_name,
                                user=db_user,
                                password=db_password
                            )
                    grok_management_key=(cred_manager.get_credential()).get("grok_management_key","")
                    GROK_COLLEC_MANAGEMENT_OBJ=GrokCollectionManager(grok_management_key=grok_management_key)
                    derived_collection_name=AutomaticFileToCollection.get_collection_name(topic)
                    derived_collection_id_obj=(GROK_COLLEC_MANAGEMENT_OBJ.create_grok_collection(user_assigned_collection_name=derived_collection_name))
                    if(not derived_collection_id_obj.get("status",False)):
                        rich_print(f"Unable to create collection...{'Xai SERVER INTERNAL PROBLEM' if derived_collection_id_obj.get('status_code')>499 else ''}",style="danger")
                        exit()
                    topic_id = self.db.create_topic(topic=topic,collection_name=derived_collection_name,collection_id=derived_collection_id_obj.get("collection_id",""))
                    if topic_id:
                        text = "[bold green]Topic Created Successfully![/bold green]"
                        info_text = f"[dim]Topic '{topic}' has been added to the system[/dim]"
                        
                        panel = Panel(
                            f"{text}\n\n{info_text}",
                            border_style="green",
                            title="Success",
                            expand=True,
                        )
                        console.print(panel)
                        
                        import time
                        time.sleep(2)
                        
                        # Set as current topic
                        self.db.set_current_topic(topic)
                        return topic
                    else:
                        console.print("[red]Failed to create topic. Please try again.[/red]")
                        continue
                
            elif choice == "2":
                history = self.db.get_history_topics()
                if not history:
                    console.print("[yellow]No topics found. Please create a topic first.[/yellow]")
                    import time
                    time.sleep(2)
                    continue
                
                # Create list for History with a Back option
                history_choices = [Choice(value=t, name=t) for t in history]
                history_choices.append(Choice(value="back", name="[Go Back]"))
                
                topic_selection = inquirerPY.select(
                    message="Select Topic from History:",
                    choices=history_choices,
                    pointer="▶"
                ).execute()
                
                if topic_selection == "back":
                    continue
                
                # Set as current topic
                self.db.set_current_topic(topic_selection)
                return topic_selection
    
    def get_chat_options(self) -> Dict[str, Any]:
        """
        Get comprehensive chat options including topic selection and configuration
        Returns dictionary with selected topic and other options
        """
        # Initialize database and ensure tables exist
        self.db.init_db()
        
        # Get the selected topic
        selected_topic = self.get_chat_topic()
        
        # Get topic details
        topic_data = self.db.get_topic_by_name(selected_topic)
        
        # Return comprehensive options
        return {
            'topic': selected_topic,
            'topic_details': topic_data,
            'collection_name': topic_data['collection_name'] if topic_data else None,
            'collection_id': topic_data['collection_id'] if topic_data else None,
            'knowledge_base_files': topic_data['knowledge_base_files'] if topic_data else None
        }

# ==================== USAGE EXAMPLE ====================
def topic_selected_print_console(current_topic:str):
    status_panel = Panel(f"[bold white]Active Chat Topic: {current_topic}[/bold white]",style="white on magenta",expand=True,border_style="magenta")    
    console.print("\n")
    console.print(status_panel)

def leaf_selected_topic():
    """Example usage of the database interactions and CLI"""
    # Initialize database connection
    db = ALL_SQL_INTERACTIONS()
    
    try:
        # Initialize CLI component
        cli = TopicSelectorCLI(db)
        
        # Option 1: Just get the topic name
        # console.print("[bold cyan]Option 1: Get just the topic name[/bold cyan]")
        current_topic = cli.get_chat_topic()
        
        # Display status panel
        status_panel = Panel(
            f"[bold white]Active Chat Topic: {current_topic}[/bold white]",
            style="white on magenta",
            expand=True,
            border_style="magenta"
        )    
        console.print("\n")
        console.print(status_panel)
        
        # Option 2: Get comprehensive chat options
        # console.print("\n[bold cyan]Option 2: Get comprehensive chat options[/bold cyan]")
        # Uncomment to use the comprehensive options
        # chat_options = cli.get_chat_options()
        # console.print(f"[green]Selected Topic: {chat_options['topic']}[/green]")
        # console.print(f"[dim]Collection: {chat_options['collection_name']}[/dim]")
        
        # Return the selected topic for use in your main script
        return current_topic
        
    finally:
        # Close database connection
        db.close()


class AutomaticFileToCollection:
    @staticmethod
    def get_collection_name(input_string):
        # 1. Filter: Keep only alphanumeric characters (A-Z, a-z, 0-9)
        cleaned = "".join(char for char in input_string if char.isalnum())
        # 2. Generate: Create a random UUID
        unique_id = str(uuid.uuid4())
        modified_collection_name=f"{cleaned}_{unique_id}"
        if len(modified_collection_name)>50:
            modified_collection_name=modified_collection_name[:(50-len(modified_collection_name))]
        # 3. Postfix: Combine the cleaned string with the UUID
        # Using an underscore as a separator for readability
        return modified_collection_name
    
    @staticmethod
    def expand_directories_and_set_filter_flag(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post-process first-step output:
        - Detects directories in FILEPATHS
        - Sets FOLDER_FILES_FILTER_AND_STRUCTURE_CHECK_NEEDED = True if any dirs found
        - Replaces every directory with all its leaf files (recursive, including sub-folders)
        - Removes duplicate files
        - Leaves FILE_EMBEDDING_REQUIRED unchanged
        """
        if "FILEPATHS" not in analysis_data or not analysis_data["FILEPATHS"]:
            analysis_data["FOLDER_FILES_FILTER_AND_STRUCTURE_CHECK_NEEDED"] = False
            return analysis_data

        original_filepaths = analysis_data["FILEPATHS"]
        new_filepaths: List[str] = []
        has_dirs = False
        cwd = Path.cwd()

        for p_str in original_filepaths:
            # Normalize path
            if p_str in {".", "./", ""}:
                p = cwd
            else:
                p = Path(p_str)

            if p.is_dir():
                has_dirs = True
                for root, _, files in os.walk(p):
                    for filename in files:
                        full_file = Path(root) / filename
                        
                        # Keep the same style user expects (relative vs absolute)
                        if str(p_str).startswith(("./", ".")) or p == cwd:
                            try:
                                rel = full_file.relative_to(cwd)
                                new_filepaths.append(f"./{rel.as_posix()}")
                            except ValueError:
                                new_filepaths.append(full_file.as_posix())
                        else:
                            new_filepaths.append(full_file.as_posix())
            else:
                # It's a file (or non-existent path) → keep as-is
                new_filepaths.append(p_str)

        # Deduplicate while preserving order
        analysis_data["FILEPATHS"] = list(dict.fromkeys(new_filepaths))
        analysis_data["FOLDER_FILES_FILTER_AND_STRUCTURE_CHECK_NEEDED"] = has_dirs

        return analysis_data

    @staticmethod
    def safe_delete_paths(paths_to_delete: List[str]) -> Dict:
        """
        Safely delete multiple files and/or directories
        
        Args:
            paths_to_delete: List of file or directory paths to delete
        
        Returns:
            Dictionary containing:
            - status: 'success' or 'partial' or 'failed'
            - deleted: List of successfully deleted paths
            - failed: List of paths that failed to delete with reasons
            - summary: Summary statistics
        """
        import os
        import shutil
        from pathlib import Path
        
        deleted = []
        failed = []
        
        for path_name in paths_to_delete:
            path = Path(path_name)
            
            # Skip if path doesn't exist
            if not path.exists():
                failed.append({
                    "path": path_name,
                    "reason": "Path does not exist"
                })
                continue
            
            try:
                # Check if it's a file or directory
                if path.is_file():
                    # Delete file
                    os.remove(path_name)
                    deleted.append({
                        "path": path_name,
                        "type": "file"
                    })
                elif path.is_dir():
                    # Delete directory and all contents
                    shutil.rmtree(path_name)
                    deleted.append({
                        "path": path_name,
                        "type": "directory"
                    })
                else:
                    failed.append({
                        "path": path_name,
                        "reason": "Path is neither file nor directory (might be symlink or special file)"
                    })
                    
            except PermissionError:
                failed.append({
                    "path": path_name,
                    "reason": "Permission denied"
                })
            except Exception as e:
                failed.append({
                    "path": path_name,
                    "reason": str(e)
                })
        
        # Determine overall status
        if len(deleted) == len(paths_to_delete):
            status = "success"
        elif len(deleted) > 0:
            status = "partial"
        else:
            status = "failed"
        
        return {
            "status": status,
            "deleted": deleted,
            "failed": failed,
            "summary": {
                "total": len(paths_to_delete),
                "deleted_count": len(deleted),
                "failed_count": len(failed)
            }
        }

class GrokCollectionManager:
    def __init__(self,grok_management_key:str):
        self.GROK_MANAGEMENT_KEY=grok_management_key

    def create_grok_collection(self,user_assigned_collection_name:str)->Dict[str,Any]:

        url = "https://management-api.x.ai/v1/collections"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.GROK_MANAGEMENT_KEY}"
        }
        payload = {
            "collection_name": user_assigned_collection_name
        }
        response = requests.post(url, headers=headers, json=payload)
        # Print response for debugging
        if response.status_code == 200 or response.status_code == 201:
            return {"status":True,"collection_id":response.json().get("collection_id")}
        else:
            return {"status":False,"status_code":response.status_code}

    def list_xai_collections(self):

        if self.GROK_MANAGEMENT_KEY is None:
            return {"resposne_success":False,"data":{}}

        else:
            url = "https://management-api.x.ai/v1/collections"
            headers = {
                "Authorization": f"Bearer {self.GROK_MANAGEMENT_KEY}"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            if response.status_code>=200 and response.status_code<=299:
                data={}
                list_of_collections=response.json().get("collections",{})
                for a_collection_obj in list_of_collections:
                    data[f"{a_collection_obj.get('collection_name')}"]=a_collection_obj.get("collection_id")

                return {"resposne_success":True,"data":data}
            else:
                return {"resposne_success":False,"data":{}}
        
    def upload_file_simple(self, collection_id: str,file_paths:list[str])->List:
            """
            Prompts for a file path and uploads it to a collection 
            without any extra metadata.
            """
            # 1. Prompt for file location
            FILE_UPLOADED_DETAILS: List[Any] = []
            
            for file_path in file_paths:
                FILE_DETAILS_OBJ: Dict[str, Optional[str]] = {"file_name": None, "file_id": None}
            # 2. Prepare Request
                url = f"https://management-api.x.ai/v1/collections/{collection_id}/documents"
                headers = {
                    "Authorization": f"Bearer {self.GROK_MANAGEMENT_KEY}"
                }

                # Get the filename from the path automatically
                filename = os.path.basename(file_path)

                try:
                    with open(file_path, 'rb') as f:
                        # The 'data' key in files matches the -F "data=@..." from the curl
                        files = {
                            'data': (filename, f)
                        }
                        # The 'name' field tells the collection what to call the file
                        extension="txt"
                        if (len(filename.split("."))>1):
                            extension=filename.split(".")[-1].strip()
                        payload = {
                            'name': filename,
                            'field':{'device_doc_name':filename},
                            'content_type':"application/"+extension
                        }
                        time.sleep(3)
                        response = requests.post(url, headers=headers, data=payload, files=files)

                    if response.status_code in [200, 201]:
                        FILE_DETAILS_OBJ["file_name"]=filename
                        FILE_DETAILS_OBJ["file_id"]=response.json().get("file_metadata",{}).get("file_id",None)
                        FILE_UPLOADED_DETAILS.append(FILE_DETAILS_OBJ)
                        rich_print(f"Successfully Uploaded File named {filename}",style="success")
                    else:
                        # rich_print(msg=f"[{filename}]\nUpload failed: {response.text}",style="danger")
                        if("AlreadyExists".lower() in (response.text).lower()):
                            typewrite("Atempting File Delete and Upload...")
                            file_id=response.text.split("file_id:")[1].split(")")[0].strip()
                            doc_delete_succesful=self.delete_xai_document(collection_id=collection_id,document_id=file_id)
                            if(doc_delete_succesful):
                                rich_print(msg="Deleted This Doc's Previous Upload..., Now Re-Uploading...",style="success")
                                time.sleep(10)
                                response = requests.post(url, headers=headers, data=payload, files=files)
                                if response.status_code in [200, 201]:
                                    FILE_DETAILS_OBJ["file_name"]=filename
                                    FILE_DETAILS_OBJ["file_id"]=response.json().get("file_metadata",{}).get("file_id",None)
                                    FILE_UPLOADED_DETAILS.append(FILE_DETAILS_OBJ)
                                    rich_print(f"Successfully Uploaded File named {filename}",style="success")                                

                except Exception as e:
                    rich_print(f"An error occurred: {e}",style="danger")
                
            return FILE_UPLOADED_DETAILS
    
    def delete_grok_collection(self, collection_id: str) -> bool:
            """
            Permanently deletes a collection from the xAI management system.
            """
            if not collection_id:
                print("Error: collection_id is required.")
                return False

            url = f"https://management-api.x.ai/v1/collections/{collection_id}"
            headers = {
                "Authorization": f"Bearer {self.GROK_MANAGEMENT_KEY}"
            }

            try:
                # Send the DELETE request
                response = requests.delete(url, headers=headers)
                
                # 204 (No Content) or 200 (OK) indicate a successful deletion
                if response.status_code in [200, 204]:
                    print(f"Collection {collection_id} has been deleted.")
                    return True
                else:
                    print(f"Delete failed: {response.status_code} - {response.text}")
                    return False
                    
            except Exception as e:
                print(f"An error occurred during deletion: {e}")
                return False

    def check_file_status(self,collection_id: str, file_id: str):
            url = f"https://management-api.x.ai/v1/collections/{collection_id}/documents/{file_id}"
            headers = {
                "Authorization": f"Bearer {self.GROK_MANAGEMENT_KEY}"
            }

            try:
                response = requests.get(url, headers=headers)
                
                if (response.status_code >= 200) and (response.status_code <= 299):
                    data = response.json()
                    # print(json.dumps(data,indent=4))
                    # print(data.get("status","DOCUMENT_STATUS_FAILED"))
                    # Status is located in the top level of the document object
                    return {"status":data.get("status","DOCUMENT_STATUS_FAILED"),"error_message":"..."}
                else:
                    return {"status":data.get("status","DOCUMENT_STATUS_FAILED"),"error_message":data.get("error_message","None")}
                    
            except Exception as e:
                return {"status":"REQUEST_FAILURE","error_message":"Failed at making request..."}

    def delete_xai_document(self,collection_id, document_id):
        
        if not self.GROK_MANAGEMENT_KEY:
            raise ValueError("API Key not found. Please set XAI_MANAGEMENT_API_KEY.")
        url = f"https://management-api.x.ai/v1/collections/{collection_id}/documents/{document_id}"
        
        headers = {
            "Authorization": f"Bearer {self.GROK_MANAGEMENT_KEY}"
        }
        try:
            response = requests.delete(url, headers=headers)
            # Check if the deletion was successful (usually 200 or 204)
            if response.status_code in [200, 204]:
                return True
            else:
                return False
        except requests.exceptions.RequestException as e:
            return False

    def track_processing_status(self, collection_id: str, uploaded_files: List[Dict[str, Any]]):
        """
        Takes the output of upload_file_simple and tracks their backend processing status.
        """
        if not uploaded_files:
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[filename]}"),
            BarColumn(bar_width=None, complete_style="green", finished_style="bold green"),
            TaskProgressColumn(),
            TextColumn("[white]Status: {task.fields[status]}"),
            console=Console()
        ) as progress:
            
            # Create a task for each file
            tasks = []
            for file_info in uploaded_files:
                f_id = file_info.get("file_id")
                f_name = file_info.get("file_name")
                
                if f_id:
                    task_id = progress.add_task(
                        "processing", 
                        total=100, 
                        filename=f_name, 
                        status="Initializing..."
                    )
                    tasks.append({"task_id": task_id, "file_id": f_id, "filename": f_name})

            # Poll until all files are finished
            completed_files = set()
            while len(completed_files) < len(tasks):
                for item in tasks:
                    if item["file_id"] in completed_files:
                        continue

                    # Call your existing status function
                    status_response = self.check_file_status(collection_id, item["file_id"])
                    current_status = status_response.get("status", "UNKNOWN")

                    # Update the UI based on status
                    if current_status == "DOCUMENT_STATUS_PROCESSED":
                        progress.update(item["task_id"], completed=100, status="[bold green]Done[/]")
                        completed_files.add(item["file_id"])
                    elif ("FAILED" in current_status or "ERROR" in current_status or "FAILURE" in current_status):
                        progress.update(item["task_id"], completed=100, status="[bold red]Failed[/]")
                        completed_files.add(item["file_id"])
                    else:
                        # Still processing - pulse the progress bar
                        progress.update(item["task_id"], advance=5, status=f"[yellow]{current_status}[/]")
                        if progress.tasks[item["task_id"]].completed >= 95:
                            progress.update(item["task_id"], completed=20) # Loop visual for indefinite tasks

                time.sleep(2) # Prevent API rate limiting

# --- 1. Define Pydantic Models for Structured Output ---

class StepDetails(BaseModel):
    # Standard required fields
    use_env: List[str]
    step_name: str
    steps_to_not_include: List[str] = Field(default_factory=list)
    
    # CRITICAL: This allows the dictionary to accept the dynamic 
    # PowerShell command keys "1", "2", "3", etc.
    model_config = ConfigDict(extra="allow")

class AgenticData(BaseModel):
    step: Dict[str, StepDetails]
    uuid: Optional[str] = None  # Injected after the API call
    
    model_config = ConfigDict(extra="allow")

class InfoValue(BaseModel):
    type: str
    value: str

class PowerShellWorkflow(BaseModel):
    """The root object for the xAI Structured Output"""
    Agentic_Data: Optional[AgenticData] = None
    Info_Data: Dict[str, InfoValue] = Field(default_factory=dict)

class FileAnalysisOutput(BaseModel):
    """Root model used by BOTH first-step and second-step structured output."""
    FILE_EMBEDDING_REQUIRED: bool = Field(
        ...,
        description="True if any files are still required after all filtering/expansion."
    )
    FILEPATHS: List[str] = Field(
        default_factory=list,
        description=(
            "List of file paths OR directories. "
            "Directories are allowed (e.g. './', './somedir', 'C:/projects/myfolder/'). "
            "After the expansion step this list will contain ONLY files (no directories)."
        )
    )
    FOLDER_FILES_FILTER_AND_STRUCTURE_CHECK_NEEDED: bool = Field(
        False,
        description=(
            "First-step LLM always sets this to false. "
            "The Python expansion function will set it to true if any directories were present."
        )
    )


def interactive_credential_menu(cred_manager: CredentialManager):
    """
    Interactive menu for managing credentials using InquirerPy
    
    Args:
        cred_manager: CredentialManager instance
    """
    while True:
        # Ensure a record exists
        if not cred_manager.get_credential():
            print(" Creating initial credential record...")
            cred_manager.create_initial_record()
        
        # Display current status
        cred_manager.display_current_credentials()
        
        # Create menu choices
        main_choices = [
            Choice(value="grok_api", name="1. Set/Update Grok LLM API Key"),
            Choice(value="grok_mgmt", name="2. Set/Update Grok Management API Key"),
            Choice(value="view", name="3. View Credentials"),
            Choice(value="clear", name="4. Clear All Credentials"),
            Choice(value="back", name="5. Back to Main Menu\n"),
        ]
        
        try:
            action = inquirerPY.select(
                message="Select an option:",
                choices=main_choices,
                pointer="▶",
            ).execute()
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\n Exiting credential menu...")
            break
        
        if action == 'grok_api':
            # Set Grok API Key
            try:
                api_key = inquirerPY.text(
                    message="Enter Grok LLM API Key:",
                    validate=lambda x: len(x.strip()) > 0 or "API key cannot be empty",
                    transformer=lambda x: "✓" if len(x.strip()) > 0 else "✗"
                ).execute()
                
                if api_key and api_key.strip():
                    cred_manager.update_grok_api_key(api_key.strip())
                    print(" Grok API Key updated successfully!")
            except KeyboardInterrupt:
                print("\n Operation cancelled.")
                continue
        
        elif action == 'grok_mgmt':
            # Set Grok Management Key
            try:
                mgmt_key = inquirerPY.text(
                    message="Enter Grok Management API Key:",
                    validate=lambda x: len(x.strip()) > 0 or "Management key cannot be empty",
                    transformer=lambda x: "✓" if len(x.strip()) > 0 else "✗"
                ).execute()
                
                if mgmt_key and mgmt_key.strip():
                    cred_manager.update_grok_management_key(mgmt_key.strip())
                    print(" Grok Management Key updated successfully!")
            except KeyboardInterrupt:
                print("\n Operation cancelled.")
                continue
        
        elif action == 'view':
            # View credentials (masked)
            cred = cred_manager.get_credential()
            if cred:
                print("\n" + "="*50)
                print(" COMPLETE CREDENTIALS DETAILS")
                print("="*50)
                
                # Mask sensitive data
                def mask_string(s):
                    if s:
                        return s[:4] + "..." + s[-4:] if len(s) > 8 else "***"
                    return "Not Set"
                
                print(f" Grok API Key: {mask_string(cred['grok_api_key'])}")
                print(f" Grok Management Key: {mask_string(cred['grok_management_key'])}")
                print("="*50 + "\n")
            
            input("Press Enter to continue...")
        
        elif action == 'clear':
            # Clear all credentials
            try:
                confirm = inquirerPY.confirm(
                    message="  Are you sure you want to clear ALL credentials?",
                    default=False
                ).execute()
                
                if confirm:
                    cred_manager.update_grok_api_key(None)
                    cred_manager.update_grok_management_key(None)
                    print(" All credentials have been cleared!")
            except KeyboardInterrupt:
                print("\n Clear operation cancelled.")
                continue
        
        elif action == 'back':
            print("Returning to main menu...")
            break



##################################################################################################
                            # THE BELOW ARE FUNCTIONS FOR GROK AGENT
##################################################################################################

title_text = emoji.emojize(":robot: Jack")
user_icon = emoji.emojize(":white_question_mark: YOU")
offline_jack_chat_buuble_icon = emoji.emojize(":robot: Jack")

def rich_print(msg, style="default"):
    """
    Custom print function with 10 EXE-safe design presets.
    """
    match style:
        case "info":
            console.print(f"[bold cyan][!][/bold cyan] {msg}")
        
        case "warning":
            console.print(f"[bold yellow](!)[/bold yellow] [italic]{msg}[/italic]")
        
        case "danger":
            console.print(Panel(msg, style="white on red", box=DOUBLE, expand=False))
        
        case "success":
            console.print(f"[bold green][+][/bold green] {msg}")
            
        case "neon":
            console.print(f"[bold magenta]>>> {msg} <<<[/bold magenta]")
            
        case "panel":
            console.print(Panel.fit(msg, title="LOG", border_style="blue", box=ROUNDED))
            
        case "bold_line":
            console.print(Rule(style="bright_white"))
            console.print(msg, justify="center", style="bold")
            console.print(Rule(style="bright_white"))
            
        case "heavy":
            console.print(Panel(msg, border_style="green", box=HEAVY, title="[reverse] ITERATION DETAILS [/]"))
            
        case "midnight":
            console.print(f"[white on blue]  {msg}  [/white on blue]")
            
        case "centered":
            console.print(Align.center(f"[bold reverse white]  {msg}  [/]"))
            
        case _:
            console.print(msg)

def typewrite(msg, style="default", speed=0.05):
    """
    Prints msg character by character with safety checks for Rich markup.
    """
    style_map = {
        "info": "bold cyan",
        "warning": "bold yellow italic",
        "success": "bold green",
        "neon": "bold magenta",
        "midnight": "white on blue",
        "danger": "white on red"
    }
    
    rich_style = style_map.get(style, "")

    for char in msg:
        # If there is a style, wrap the character in tags; otherwise, print raw
        if rich_style:
            console.print(f"[{rich_style}]{char}[/]", end="")
        else:
            console.print(char, end="")
        
        # This ensures the character hits the screen immediately
        time.sleep(speed)
    
    console.print()  # Final newline

def json_controller(
    further_file_path: str,
    actionType,
    key,
    value=None,
    valueType="str",
    defaultLoc="./agentic_workflow",
    fallbackValue=None
):
    # ---------- Helper Functions ----------
    def set_nested_value(data, keys, value):
        for k in keys[:-1]:
            data = data.setdefault(k, {})
        data[keys[-1]] = value

    def get_nested_value(data, keys):
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
            else:
                return None, None

        if data is None:
            return None, None

        if isinstance(data, bool): t = "bool"
        elif isinstance(data, int): t = "int"
        elif isinstance(data, float): t = "float"
        elif isinstance(data, list): t = "array"
        elif isinstance(data, dict): t = "obj"
        else: t = "str"

        return data, t

    def convert_type(value, value_type):
        try:
            if value_type == "int":
                return int(value)
            elif value_type == "float":
                return float(value)
            elif value_type == "bool":
                return str(value).lower() in ("true", "1", "yes")
            elif value_type in ("obj", "array","list","dict"):
                return json.loads(value)
            return str(value)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"Error converting '{value}' to {value_type}: {e}")

    def infer_type(value):
        if isinstance(value, bool): return "bool"
        elif isinstance(value, int): return "int"
        elif isinstance(value, float): return "float"
        elif isinstance(value, list): return "array"
        elif isinstance(value, dict): return "obj"
        else: return "str"

    # ---------- Core Logic ----------
    if not os.path.exists(defaultLoc):
        os.makedirs(defaultLoc)

    file_path = os.path.join(defaultLoc, further_file_path)
    keys = key.split(".")

    # Load existing data
    if os.path.exists(file_path):
        with open(file_path, "r",encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    # ---------- STORE ----------
    if actionType == "store":
        val = convert_type(value, valueType)
        set_nested_value(data, keys, val)

        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

        return {
            "status": "success",
            "message": f"Successfully stored '{key}'"
        }

    # ---------- GET ----------
    elif actionType == "get":
        result, val_type = get_nested_value(data, keys)

        # If key not found → use fallback
        if result is None and val_type is None:
            if fallbackValue is not None:
                return {
                    "status": "success",
                    "value": fallbackValue,   # <-- native type
                    "type": infer_type(fallbackValue),
                    "fallback_used": True
                }
            else:
                return {
                    "status": "error",
                    "message": "Key not found"
                }

        return {
            "status": "success",
            "value": result,   # <-- native type (FIXED)
            "type": val_type,
            "fallback_used": False
        }

    # ---------- INVALID ----------
    else:
        return {
            "status": "error",
            "message": "Invalid actionType"
        }
    
def create_json_file(data_dict, file_path, indent=4):
    """
    Converts a dictionary to JSON and saves it to a specified full path.
    
    Args:
        data_dict (dict): The dictionary to convert.
        file_path (str): The full destination path (e.g., 'C:/Scripts/output.json').
        indent (int): Spaces for nested structures.
        
    Returns:
        bool: True if successful, False if failed.
    """
    try:
        # Ensure the directory exists before trying to write the file
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(file_path, 'w', encoding='utf-8') as f:
            # json.dump (no 's') writes directly to a file stream
            json.dump(data_dict, f, indent=indent, ensure_ascii=False)
        
        return True

    except Exception as e:
        return False

def pre_agentic_script(DefaultLoc: str = "./agentic_workflow",pre_executor_json_name:str="unpredictable_hyejack_powershell_file_20052000PM_agentic_task"):
    pre_powershell_script = f"""

function GetSet-SharedValue {{

    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AgenticTaskUUID,

        [Parameter(Mandatory = $true)]
        [ValidateSet("get", "store")]
        [string]$ActionType,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $false)]
        $Value,

        [Parameter(Mandatory = $false)]
        [ValidateSet("int", "float", "obj", "array", "bool", "str")]
        [string]$ValueType = "str",

        [Parameter(Mandatory = $false)]
        [string]$DefaultLoc = "{DefaultLoc}",

        [Parameter(Mandatory = $false)]
        $FallbackValue = $null
    )

    # 1. Ensure directory exists
    if (-not (Test-Path $DefaultLoc)) {{
        New-Item -Path $DefaultLoc -ItemType Directory | Out-Null
    }}

    $filePath = Join-Path $DefaultLoc "{pre_executor_json_name}_errors_$($AgenticTaskUUID).json"
    $keys = $Key.Split('.')

    # 2. Load existing data or initialize file if missing
    if (Test-Path $filePath) {{
        try {{
            $content = Get-Content $filePath -Raw
            $data = if ([string]::IsNullOrWhiteSpace($content)) {{ @{{}} }} else {{ $content | ConvertFrom-Json -AsHashtable }}
        }} catch {{
            $data = @{{}}
        }}
    }} else {{
        # Create the file immediately if it doesn't exist
        $data = @{{}}
        "{{}}" | Set-Content $filePath
    }}

    if ($ActionType -eq "store") {{
        # Type Conversion
        $convertedVal = $Value
        try {{
            switch ($ValueType) {{
                "int"   {{ $convertedVal = [int]$Value }}
                "float" {{ $convertedVal = [double]$Value }}
                "bool"  {{ $convertedVal = [System.Convert]::ToBoolean($Value) }}
                "obj"   {{ $convertedVal = $Value | ConvertFrom-Json -AsHashtable }}
                "array" {{ $convertedVal = $Value | ConvertFrom-Json }}
                "str"   {{ $convertedVal = [string]$Value }}
            }}
        }} catch {{
            Write-Error "Error converting '$Value' to $ValueType : $($_.Exception.Message)"
            return # Exit function instead of killing the session
        }}

        # Recursively set nested value
        $current = $data
        for ($i = 0; $i -lt $keys.Count - 1; $i++) {{
            $k = $keys[$i]
            if (-not $current.ContainsKey($k) -or $null -eq $current[$k]) {{
                $current[$k] = @{{}}
            }}
            $current = $current[$k]
        }}
        $current[$keys[-1]] = $convertedVal

        # Save to file
        $data | ConvertTo-Json -Depth 100 | Set-Content $filePath

    }} elseif ($ActionType -eq "get") {{
        # Recursively get nested value
        $current = $data
        foreach ($k in $keys) {{
            if ($null -ne $current -and $current.ContainsKey($k)) {{
                $current = $current[$k]
            }} else {{
                # Key not found: return FallbackValue if provided, else Error
                if ($PSBoundParameters.ContainsKey('FallbackValue')) {{
                    return $FallbackValue
                }} else {{
                    Write-Error "Key '$Key' not found and no FallbackValue provided."
                    return $null
                }}
            }}
        }}
        
        # If result is an object/array, return as JSON; otherwise return raw value
        if ($current -is [System.Collections.IDictionary] -or $current -is [System.Collections.IEnumerable] -and $current -isnot [string]) {{
            return $current | ConvertTo-Json -Depth 100 -Compress
        }}
        return $current
    }}
}}

"""
    return pre_powershell_script

def read_json_file(file_path):
    """Reads a JSON file and returns the data as a dictionary."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        return "Error: The file was not found."
    except json.JSONDecodeError:
        return "Error: Failed to decode JSON. Check if the file format is valid."

def create_file(file_name, parent_location=".", content=""):
    """Creates a file with optional content at the specified location."""
    full_path = os.path.join(parent_location, file_name)
    
    try:
        if not os.path.exists(parent_location):
            os.makedirs(parent_location)
            
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception:
        return False


def display_info_data(info_data,MSG_FROM=title_text):
    """Display Info_Data in a rich formatted way with all content in a single rounded corner panel."""
    if not info_data:
        return
    
    content_lines = []
    
    for key, value in sorted(info_data.items()):
        if isinstance(value, dict) and value.get("type") == "text":
            text_content = value.get("value", "")
            if text_content:
                content_lines.append(text_content)
    
    if not content_lines:
        return
    
    combined_content = "\n\n".join(content_lines)
    
    panel = Panel(
        Text(combined_content, style="white"),
        title=f"[bold cyan]{MSG_FROM}[/bold cyan]",
        border_style="blue",
        padding=(1, 2),
        box=ROUNDED
    )
    
    console.print("\n")
    console.print(panel)
    console.print("\n")

def user_chat_bubble(user_content:str,MSG_FROM=user_icon):
    panel = Panel(
    Text(user_content, style="white"),
    title=f"[bold cyan]{MSG_FROM}[/bold cyan]",
    border_style="blue",
    padding=(1, 2),
    box=ROUNDED
    )
    
    console.print("\n")
    console.print(panel)
    console.print("\n")


def update_error_json_with_script_status(agent_task_uuid, default_loc, script_formed,pre_executor_json_name:str="unpredictable_hyejack_powershell_file_20052000PM_agentic_task"):
    """Update the error JSON file with powershell_script_formed status."""
    error_file_path = os.path.join(default_loc, f"{pre_executor_json_name}_errors_{agent_task_uuid}.json")
    
    try:
        if os.path.exists(error_file_path):
            with open(error_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    data = json.loads(content)
                else:
                    data = {}
        else:
            data = {}
        
        data["powershell_script_formed"] = script_formed
        data["no_syntax_error"] = False
        
        with open(error_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def jsontops1(json_path,script_file_name = "powershell_hyejack_" ,default_loc="C:/Users/asrqu/OneDrive/Desktop/AGENTIC_FOLDER",agentic_task_pre_str="unpredictable_hyejack_powershell_file_20052000PM_agentic_task",script_seperate_folder_name="UNPREDICTABLE_DIR_NAME__HYJACK_POWERSHELL_POWERSHELL_SCRIPT_200520001040PM"):
    """
    Convert a JSON workflow file to a PowerShell script.
    
    Args:
        json_path (str): Path to the JSON file containing the workflow
        default_loc (str): Default location for storing generated files
    
    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the conversion was successful
            - script_path (str): Path to the generated PowerShell script (if successful)
            - error (str): Error message (if failed)
            - info_displayed (bool): Whether Info_Data was displayed
    """
    result = {
        "success": False,
        "script_path": None,
        "error": None,
        "info_displayed": False
    }
    
    try:
        powershell_content = ""
        script_formed = False
        
        my_data = read_json_file(json_path)
        
        if isinstance(my_data, str) and my_data.startswith("Error:"):
            result["error"] = my_data
            return result
        
        # Display Info_Data if present
        if my_data.get("Info_Data", False):
            display_info_data(my_data.get("Info_Data"))
            result["info_displayed"] = True
        
        if my_data.get("Agentic_Data", False):
            agent_task_uuid = my_data.get("Agentic_Data").get("uuid")
            if not agent_task_uuid:
                result["error"] = "Agentic_Data missing 'uuid' field"
                return result
                
            script_file_name += f"{agent_task_uuid}.ps1"
            
            for a_key, a_value in my_data.get("Agentic_Data", False).get("step", {}).items():
                try:
                    int(a_key)
                    steps_to_not_include_for_this_step=my_data.get("Agentic_Data").get("step").get(a_key).get("steps_to_not_include",[])
                    for a_sub_step, a_sub_step_value in a_value.items():
                        if a_sub_step not in steps_to_not_include_for_this_step:
                            try:
                                int(a_sub_step)
                                powershell_content += f"""try {{ 
                                    {a_sub_step_value}
                                }}
                                catch{{
                                    $total_iteration = GetSet-SharedValue -AgenticTaskUUID "{agent_task_uuid}" -ActionType get -Key "total_iteration" -FallbackValue 0
                                    $total_iteration+=1              
                                    GetSet-SharedValue -AgenticTaskUUID "{agent_task_uuid}" -ActionType store -Key "total_iteration" -Value $total_iteration -ValueType "int"
                                    GetSet-SharedValue -AgenticTaskUUID "{agent_task_uuid}" -ActionType store -Key "iteration_details.$total_iteration.failed_at" -Value "step.{a_key}.{a_sub_step}" -ValueType "str"
                                    GetSet-SharedValue -AgenticTaskUUID "{agent_task_uuid}" -ActionType store -Key "iteration_details.$total_iteration.error_msg" -Value "$_.Exception.Message" -ValueType "str"
                                    GetSet-SharedValue -AgenticTaskUUID "{agent_task_uuid}" -ActionType store -Key "no_syntax_error" -Value "true" -ValueType "bool"
                                    exit 1
                                }}"""
                            except Exception:
                                continue
                except Exception:
                    continue
            
            powershell_content += f"""
            GetSet-SharedValue -AgenticTaskUUID "{agent_task_uuid}" -ActionType store -Key "completed" -Value "true" -ValueType "bool"
            """
            pre_powershell_script = pre_agentic_script(DefaultLoc=default_loc)
            powershell_content = f"{pre_powershell_script}\n{powershell_content}"
            
            script_full_path = os.path.join(default_loc, script_seperate_folder_name, script_file_name)
            script_created = create_file(script_file_name, f"{default_loc}/{script_seperate_folder_name}", powershell_content)
            
            if script_created:
                script_formed = True
                result["success"] = True
                result["script_path"] = script_full_path
            else:
                result["error"] = "Failed to create PowerShell script file"
            
            update_error_json_with_script_status(agent_task_uuid, default_loc, script_formed,pre_executor_json_name=agentic_task_pre_str)
        else:
            result["success"] = True
            result["error"] = "No Agentic_Data found in JSON"
            
    except Exception as e:
        result["error"] = str(e)
    
    return result

def adv1_usertojson(
    model: str,
    query: str,
    api_key: str,
    common_uuid: str,
    TOMLOBJ: Dict,
    system_prompt: Optional[str] = None,
    assistant_context: Optional[str] = None,
    chat_history: Optional[List[Dict]] = None,
    websearch: bool = False,
    collections_search: bool = False,
    xsearch: bool = False,
    code_interpreter: bool = False,
    fullpower: bool = False,
    fullpower2X: bool = False,
    vector_store_ids: Optional[List[str]] = None,
    max_num_results: int = 10,
    trythreshold=5
) -> Dict[str, Any]:
    RESPONSETRYCOUNT = 0
    REQUEST_GO_ON = True
    url = "https://api.x.ai/v1/responses"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    if fullpower:
        websearch = xsearch = code_interpreter = collections_search = True
        max_num_results = 25 if max_num_results < 25 else max_num_results
    elif fullpower2X:
        websearch = xsearch = code_interpreter = collections_search = True
        max_num_results = 50 if max_num_results < 50 else max_num_results

    # ====================== Build Tools ======================
    tools = []
    if websearch:
        tools.append({"type": "web_search"})
    if xsearch:
        tools.append({"type": "x_search"})
    if code_interpreter:
        tools.append({"type": "code_interpreter"})
    if collections_search:
        if not vector_store_ids or vector_store_ids == []:
            vector_store_ids = []
        
        tools.append({
            "type": "file_search",
            "vector_store_ids": vector_store_ids,
            "max_num_results": max_num_results
        })

    # ====================== Build Smart System Prompt ======================
    final_system_prompt = system_prompt or ""
    tool_instructions = []

    if collections_search:
        tool_instructions.append(
            TOMLOBJ["COLLLECTION_SEARCH_PROMPT"]
        )

    if websearch:
        tool_instructions.append(
            TOMLOBJ["WEB_SEARCH_PROMPT"]
        )

    if xsearch:
        tool_instructions.append(
            TOMLOBJ["X_SEARCH_PROMPT"]
        )

    if code_interpreter:
        tool_instructions.append(
            TOMLOBJ["CODE_INTERPRETER_PROMPT"]
        )

    # ====================== Cross-tool Intelligence ======================
    enabled_tools = []
    if websearch: enabled_tools.append("web_search")
    if xsearch: enabled_tools.append("x_search")
    if code_interpreter: enabled_tools.append("code_interpreter")
    if collections_search: enabled_tools.append("file_search")

    if len(enabled_tools) > 1:
        cross_tool_instruction = (
            "\n\nYou can use multiple tools together if needed. "
            "For example:\n"
            "- After retrieving file content, use web_search to cross-verify facts if relevant.\n"
            "- Use code_interpreter to analyze or process data extracted from files.\n"
            "- Use x_search for latest discussions related to the topic.\n"
            "Use tools wisely and only when they genuinely help provide a better answer."
        )
    else:
        cross_tool_instruction = ""

    # Append all instructions
    if tool_instructions:
        instructions_text = "\n\n".join(tool_instructions)
        if final_system_prompt:
            final_system_prompt = final_system_prompt.strip() + "\n\n" + instructions_text
        else:
            final_system_prompt = instructions_text

    if cross_tool_instruction:
        final_system_prompt = final_system_prompt.strip() + cross_tool_instruction

    # ====================== Build Messages ======================
    messages = []
    if final_system_prompt:
        messages.append({"role": "system", "content": final_system_prompt})
    if chat_history:
        messages.extend(chat_history)
    if assistant_context:
        messages.append({"role": "assistant", "content": assistant_context})
    messages.append({"role": "user", "content": query})

    # ====================== Payload ======================
    payload = {
        "model": model,
        "input": messages,
        "tools": tools,
        "temperature": 0,
    }

    # Disable structured JSON when tools are active (more stable)
    if not tools:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "powershell_workflow",
                "strict": True,
                "schema": PowerShellWorkflow.model_json_schema()
            }
        }

    # ====================== Execution ======================
    wrapped_json = {"json_derived": False, "data": None}
    stop_animation = threading.Event()

    def animate_loading():
        frames_3 = [".", ":", ":.", "::", "::.", ":::", ":::.", "::::", "::::.", ":::::", ":::::.", "::::::", "::::::.", ":::::::", ":::::::.", "::::::::", "::::::::.", ":::::::::", ":::::::::.", "::::::::::", "::::::::::.", ":::::::::", ":::::::::.", "::::::::", "::::::::.", ":::::::", ":::::::.", "::::::", "::::::.", ":::::", ":::::.", "::::", "::::.", ":::", ":::.", "::", "::.", ":", ":.", "."]
        i = 0
        while not stop_animation.is_set():
            # Build the loading message with DCR_ANI style
            msg = Text()
            msg.append("Jack is thinking ", style="bold blue")
            msg.append(" ", style="white")
            msg.append(" [", style="bold white")
            msg.append(f"{frames_3[i % len(frames_3)]}", style="bold green")
            msg.append("]", style="bold white")
            
            # Clear line and display
            sys.stdout.write("\r" + " " * 80 + "\r")
            console.print(msg, end="")
            sys.stdout.flush()
            
            time.sleep(0.07)
            i += 1

    animation_thread = threading.Thread(target=animate_loading, daemon=True)
    animation_thread.start()
    
    while RESPONSETRYCOUNT < trythreshold:
        RESPONSETRYCOUNT += 1
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            
            resp_json = response.json()

            
            raw_content = None
            if 'choices' in resp_json and resp_json.get('choices'):
                raw_content = resp_json['choices'][0]['message']['content']
            elif 'output' in resp_json:
                for item in resp_json['output']:
                    if isinstance(item, dict) and item.get('type') == 'message':
                        for content in item.get('content', []):
                            if content.get('type') == 'output_text':
                                raw_content = content.get('text')
                                break
                        if raw_content:
                            break

            if not raw_content:
                raise ValueError("Could not extract content from API response")

            # Structured mode (PowerShell workflow)
            workflow_obj = PowerShellWorkflow.model_validate_json(raw_content)
            if workflow_obj.Agentic_Data:
                workflow_obj.Agentic_Data.uuid = common_uuid
            wrapped_json["data"] = workflow_obj.model_dump()
            
            wrapped_json["json_derived"] = True
            stop_animation.set()
            animation_thread.join(timeout=0.5)
            sys.stdout.write("\r" + " " * 80 + "\r")
            console.print("[bold green][+][/bold green] Jack is ready!", style="bold green")
            break
        except Exception as e:
            stop_animation.set()
            animation_thread.join(timeout=0.5)
            sys.stdout.write("\r" + " " * 80 + "\r")
            rich_print(f"Error occurred:\n{e}\n", style="warning")
            if RESPONSETRYCOUNT < trythreshold:
                typewrite("TRYING TO RESOLVE JSON STRUCTURE FAILURE IN THIS ITERATION...", style="info")
                # Restart animation for retry
                stop_animation.clear()
                animation_thread = threading.Thread(target=animate_loading, daemon=True)
                animation_thread.start()
            time.sleep(5)
            continue

    return wrapped_json

def run_pwsh_script(script_path):
    """
    Executes a PowerShell 7 (Core) script.
    Returns True if successful, False if an error occurs.
    """
    try:
        # We use 'pwsh' to specifically target PowerShell 7 Core
        # -ExecutionPolicy Bypass ensures the script runs regardless of local restrictions
        # -File specifies the path to the script
        result = subprocess.run(
            ["pwsh", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output=True, # Captures stdout and stderr
            text=True,           # Returns output as string instead of bytes
            check=True           # Raises CalledProcessError if return code != 0
        )
        
        # If you want to see the script's output in your console:
        if result.stdout:
            print(result.stdout)
            
        return {"status":True,"msg":"Script Executed"}

    except subprocess.CalledProcessError as e:
        # This block catches errors returned BY PowerShell (exit codes > 0)
        # \U0000274C is the Cross Mark emoji (❌)
        return {"status":False,"msg":e.stderr}

    except FileNotFoundError:
        # This block catches cases where 'pwsh' is not installed/in PATH
        return {"status":False,"msg":"\r\U0000274C Error: PowerShell 7 (pwsh) not found on this system.\n"}

    except Exception as e:
        # Catch-all for other unexpected issues
        return {"status":False,"msg":str(e)}

##################################################################################################
                            # THE ABOVE ARE FUNCTIONS FOR GROK AGENT
##################################################################################################

def user_to_json_before_main_execution(
    model: str,
    query: str,
    api_key: str,
    step_type: str,                    # "FIRST_STEP" or "SECOND_STEP"
    common_uuid: Optional[str] = None,
    expanded_filepaths: Optional[List[str]] = None,
    folder_check_needed: bool = False,
    system_prompt: Optional[str] = None,
    assistant_context: Optional[str] = None,
    chat_history: Optional[List[Dict]] = None,
    max_tokens: int = 8192,            # NEW: Help prevent truncation
) -> Dict[str, Any]:
    """
    Unified function for FIRST_STEP and SECOND_STEP with better handling for truncation.
    """
    if step_type not in ["FIRST_STEP", "SECOND_STEP"]:
        raise ValueError("step_type must be 'FIRST_STEP' or 'SECOND_STEP'")

    url = "https://api.x.ai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    json_schema = {
        "name": "file_analysis_output",
        "strict": True,
        "schema": FileAnalysisOutput.model_json_schema()
    }

    # ====================== Prepare Messages ======================
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if chat_history:
        messages.extend(chat_history)
    if assistant_context:
        messages.append({"role": "assistant", "content": assistant_context})

    if step_type == "FIRST_STEP":
        user_content = query
        animation_message = "Jack is analyzing prompt for files"
        default_system = ""
    else:  # SECOND_STEP
        if expanded_filepaths is None:
            expanded_filepaths = []
        
        # Limit the number of files sent to prevent extremely long prompts
        file_list_str = json.dumps(expanded_filepaths[:800])  # Safety limit
        
        user_content = f"""Original user request:
{query}

Expanded file list (directories already recursively expanded - showing up to 800 files):
{file_list_str}

Current value of FOLDER_FILES_FILTER_AND_STRUCTURE_CHECK_NEEDED: {folder_check_needed}

Perform final filtering: remove unsupported media/binary formats and keep only relevant files."""
        
        animation_message = "Jack is running final file filter"
        default_system = ""

    messages.append({"role": "user", "content": user_content})

    if not system_prompt:
        system_prompt = default_system
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] = system_prompt
        else:
            messages.insert(0, {"role": "system", "content": system_prompt})

    payload = {
        "model": model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema
        },
        "temperature": 0,
        "max_tokens": max_tokens,          # NEW: Important for long outputs
    }

    wrapped_json: Dict[str, Any] = {"json_derived": False, "data": None}
    stop_animation = threading.Event()

    def DCR_ANI():
        frames_3 = [".", ":", ":.", "::", "::.", ":::", ":::.", "::::", "::::.", ":::::", ":::::.", "::::::", "::::::.", ":::::::", ":::::::.", "::::::::", "::::::::.", ":::::::::", ":::::::::.", "::::::::::", "::::::::::.", ":::::::::", ":::::::::.", "::::::::", "::::::::.", ":::::::", ":::::::.", "::::::", "::::::.", ":::::", ":::::.", "::::", "::::.", ":::", ":::.", "::", "::.", ":", ":.", "."]
        i = 0
        while not stop_animation.is_set():
            # Build the loading message
            msg = Text()
            msg.append(f"{animation_message} ", style="bold blue")
            msg.append(" ", style="white")
            msg.append(" [", style="bold white")
            msg.append(f"{frames_3[i % len(frames_3)]}", style="bold green")
            msg.append("]", style="bold white")
            
            # Clear line and display
            sys.stdout.write("\r" + " " * 80 + "\r")
            console.print(msg, end="")
            sys.stdout.flush()
            
            time.sleep(0.07)
            i += 1

    animation_thread = threading.Thread(target=DCR_ANI, daemon=True)
    animation_thread.start()

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        
        raw_content = response.json()['choices'][0]['message']['content'].strip()

        # === Improved JSON parsing with fallback ===
        try:
            analysis_obj = FileAnalysisOutput.model_validate_json(raw_content)
            parsed_data = analysis_obj.model_dump()
        except Exception as parse_error:
            print(f"\n⚠️  Pydantic validation failed: {parse_error}")
            # Fallback: Try to fix common truncation issues
            if raw_content.endswith('"') is False and '"' in raw_content:
                raw_content = raw_content.rstrip() + '"]}'
            try:
                fixed_data = json.loads(raw_content)
                # Re-validate with Pydantic after manual fix attempt
                analysis_obj = FileAnalysisOutput.model_validate(fixed_data)
                parsed_data = analysis_obj.model_dump()
                print("✅ Fixed truncated JSON using fallback parser")
            except:
                print("❌ Could not recover from truncated JSON")
                raise parse_error

        if common_uuid:
            parsed_data["uuid"] = common_uuid
            
        wrapped_json["data"] = parsed_data
        wrapped_json["json_derived"] = True
        
        # Show success message
        sys.stdout.write("\r" + " " * 80 + "\r")
        console.print(f"[bold green][+][/bold green] {animation_message}   \[DONE!]{' ' * 20}", style="bold green")

    except Exception as e:
        print(f"\n❌ {step_type} Error: {str(e)}")
        if 'raw_content' in locals():
            print(f"Raw Response received: {raw_content[:500]}...")  # Show partial
    finally:
        stop_animation.set()
        animation_thread.join(timeout=0.5)
        sys.stdout.write("\r" + " " * 80 + "\r")
    
    return wrapped_json

def hyjackPowershell(MY_KEY:str,GROK_MANAGEMENT_KEY:str,TOPIC_NAME:str,Query:str,DBMANAGEROBJ:ALL_SQL_INTERACTIONS,TOMLOBJ:Dict,DefaultLoc:str="C:/Users/asrqu/OneDrive/Desktop/AGENTIC_FOLDER",TRYCOUNT:int=20,chat_history: List[Dict] | None = None,vector_store_ids: List[str] | None = None,max_num_results: int = 10,fullpower: bool = False,fullpower2X: bool = False,code_interpreter: bool = False,xsearch: bool = False,collections_search: bool = False,websearch: bool = False):
    common_uuid=str(uuid.uuid4())
    MY_MODEL = TOMLOBJ["GROK_MODEL_NAME"]
    agentic_task_pre_str="unpredictable_hyejack_powershell_file_20052000PM_agentic_task"
    agentic_task_ps1_pre_script_file_name="powershell_hyejack_"
    ps1_script_isolated_folder_name="UNPREDICTABLE_DIR_NAME__HYJACK_POWERSHELL_POWERSHELL_SCRIPT_200520001040PM"

    botoruser_reply:Dict[str,str]={"role": "assistant", "content": ""}
    modified_chat_hitory:List[Dict]=[]

    if chat_history:
        for a_history in chat_history:
            if a_history.get("content",""):
                if a_history.get("is_bot",False):
                    botoruser_reply["role"]="assistant"   
                else:
                    botoruser_reply["role"]="user"
                botoruser_reply["content"]=a_history["content"] 
            modified_chat_hitory.append(botoruser_reply)
            continue

    FILES_TO_DELETE:list[str]=[f"{DefaultLoc}/{ps1_script_isolated_folder_name}"]

    ps1_script_full_path=f"{DefaultLoc}/{ps1_script_isolated_folder_name}/{agentic_task_ps1_pre_script_file_name}{common_uuid}.ps1"
    agentic_task_jsonPath=f"{DefaultLoc}/{agentic_task_pre_str}_{common_uuid}.json"
    
    self_heal_till_eternity=True
    run_agentic_iteration_count=0
    TOTAL_ITERATION_COUNT=TRYCOUNT

    a_collection_name=TOPIC_NAME

    # --- 2. THE SYSTEM PROMPTS ---
    SYSTEM_PROMPT_FIRST_STEP = TOMLOBJ["SYSTEM_PROMPT_FIRST_STEP"]
    SECOND_SYSTEM_PROMPT = TOMLOBJ["SECOND_SYSTEM_PROMPT"]
    SYSTEM_PROMPT=TOMLOBJ["SYSTEM_PROMPT"]

    this_topic_obj_value:Dict=DBMANAGEROBJ.get_topic_by_name(topic_name=TOPIC_NAME)
    this_topics_kb_str:str=this_topic_obj_value.get("knowledge_base_files","")

    result1 = user_to_json_before_main_execution(
        model=MY_MODEL,
        query=Query,
        api_key=MY_KEY,
        step_type="FIRST_STEP",
        system_prompt=SYSTEM_PROMPT_FIRST_STEP,   # your first prompt
    )

    if result1["json_derived"]:
        # 2. Expand directories + set flag
        expanded = AutomaticFileToCollection.expand_directories_and_set_filter_flag(result1["data"])
        

        result2 = user_to_json_before_main_execution(
            model=MY_MODEL,
            query=Query,                         # original query
            api_key=MY_KEY,
            step_type="SECOND_STEP",
            expanded_filepaths=expanded["FILEPATHS"],
            folder_check_needed=expanded["FOLDER_FILES_FILTER_AND_STRUCTURE_CHECK_NEEDED"],
            system_prompt=SECOND_SYSTEM_PROMPT         # your second prompt
        )
        if result2["json_derived"]:
            EMBED_FILE_DECISION = result2["data"]
            if EMBED_FILE_DECISION.get("FILE_EMBEDDING_REQUIRED", False):
                
                # THIS IS FOR GROK FILE UPLOAD TO COLLECTION
                A_GROK_COLLECTION_MANAGER_OBJ = GrokCollectionManager(grok_management_key=GROK_MANAGEMENT_KEY)

                this_topic_obj:Dict=DBMANAGEROBJ.get_topic_by_name(topic_name=TOPIC_NAME)
                c_id=this_topic_obj.get("collection_id","")
                
                # DECIDE WHICH FILES TO UPLOAD
                predicted_files_to_upload=GrokKnowledgeBaseFileManager.get_files_with_write_time(filepaths=EMBED_FILE_DECISION.get("FILEPATHS"))
                # real files to upload after dummy cache action
                real_files_to_upload=GrokKnowledgeBaseFileManager.compare_file_states(old_list_str=this_topics_kb_str,new_list=predicted_files_to_upload)
                


                # ADD NEW KNOWLEDGE BASE RECORD


                # 2. Upload Files
                uploaded_files = A_GROK_COLLECTION_MANAGER_OBJ.upload_file_simple(
                    collection_id=c_id,
                    file_paths=real_files_to_upload["new_files_to_be_uploaded"]
                )
                # 3. Track Status with Green Bars
                if uploaded_files:
                    A_GROK_COLLECTION_MANAGER_OBJ.track_processing_status(c_id, uploaded_files)
                    DBMANAGEROBJ.update_knowledge_base_by_topic_name(topic_name=TOPIC_NAME,knowledge_base_files=real_files_to_upload["knowledge_base_total_upload_till_now_str"])

                    # Delete previous versions of the to be uploaded files

                    # --------------
                    # --------------
                    # --------------
                    # --------------
                    # --------------

    pre_agentic_task_json_result = adv1_usertojson(MY_MODEL, Query, MY_KEY, common_uuid=common_uuid,system_prompt=SYSTEM_PROMPT,chat_history=modified_chat_hitory,vector_store_ids=vector_store_ids,max_num_results=max_num_results,fullpower=fullpower,fullpower2X=fullpower2X,code_interpreter=code_interpreter,xsearch=xsearch,collections_search=collections_search,websearch=websearch,TOMLOBJ=TOMLOBJ)
    while((self_heal_till_eternity and (run_agentic_iteration_count < TOTAL_ITERATION_COUNT) )):
        if (pre_agentic_task_json_result.get("json_derived",False)):
            if (len(pre_agentic_task_json_result.get("data",{}))>0 ):
                if((pre_agentic_task_json_result.get("data").get("Agentic_Data",{})!=None) and (pre_agentic_task_json_result.get("data").get("Agentic_Data",{}).get("step",{})!=None) ):
                    if ( (len(pre_agentic_task_json_result.get("data").get("Agentic_Data",{}))==0)  and (len(pre_agentic_task_json_result.get("data").get("Agentic_Data",{}).get("step",{}))==0) ):
                        self_heal_till_eternity=False
                    else:
                        pass      
                else:
                    pass        
            else:
                break
            successfully_created_agentic_task_json = create_json_file(pre_agentic_task_json_result.get("data",{}), agentic_task_jsonPath)
            FILES_TO_DELETE.append(agentic_task_jsonPath)
            if (successfully_created_agentic_task_json):
                agentic_task_ps1_result = jsontops1(agentic_task_jsonPath,script_file_name=agentic_task_ps1_pre_script_file_name,default_loc=DefaultLoc,agentic_task_pre_str=agentic_task_pre_str)
                if (agentic_task_ps1_result.get("success",False)):
                    # here print the try iteration
                    run_agentic_iteration_count+=1
                    # rich_print(f"Iteration no:{run_agentic_iteration_count}\n{}","heavy")
                    success = run_pwsh_script(ps1_script_full_path)
                    NO_SYNTAX_ERROR_IN_PS1_SCRIPT=json_controller(further_file_path=f"{agentic_task_pre_str}_errors_{common_uuid}.json",actionType="get",key="no_syntax_error",defaultLoc=DefaultLoc,fallbackValue=False)

                    FILES_TO_DELETE.append(f"{agentic_task_pre_str}_errors_{common_uuid}.json")
                    if ( ( not success.get("status",False) ) and (not self_heal_till_eternity)):
                        total_iteration=json_controller(further_file_path=f"{agentic_task_pre_str}_errors_{common_uuid}.json",actionType="get",key="total_iteration",defaultLoc=DefaultLoc)
                        total_iteration=total_iteration.get("value",0)
                        if (not NO_SYNTAX_ERROR_IN_PS1_SCRIPT.get("value",False)):
                            total_iteration+=1
                            json_controller(further_file_path=f"{agentic_task_pre_str}_errors_{common_uuid}.json",actionType="store",key="total_iteration",defaultLoc=DefaultLoc,value=total_iteration,valueType="int")
                            
                            failed_at="Detect the step that resulted in the error"
                            error_msg=success.get("msg","Unknown Error Msg")
    
                            json_controller(further_file_path=f"{agentic_task_pre_str}_errors_{common_uuid}.json",actionType="store",key=f"iteration_details.{total_iteration}.failed_at",defaultLoc=DefaultLoc,value=failed_at,valueType="str")
                            json_controller(further_file_path=f"{agentic_task_pre_str}_errors_{common_uuid}.json",actionType="store",key=f"iteration_details.{total_iteration}.error_msg",defaultLoc=DefaultLoc,value=error_msg,valueType="str")

                        else:
                            failed_at=json_controller(further_file_path=f"{agentic_task_pre_str}_errors_{common_uuid}.json",actionType="get",key=f"iteration_details.{total_iteration}.failed_at",defaultLoc=DefaultLoc)
                            failed_at=failed_at.get("value","Failed: Unable to gather exact failure step details")
                            error_msg=json_controller(further_file_path=f"{agentic_task_pre_str}_errors_{common_uuid}.json",actionType="get",key=f"iteration_details.{total_iteration}.error_msg",defaultLoc=DefaultLoc)
                            error_msg=error_msg.get("value","Failed: Unable to gather exact details of failure")
                        
                        rich_print(f"Iteration no:{run_agentic_iteration_count}/{TOTAL_ITERATION_COUNT}\nERROR MESSAGE: {error_msg}","heavy")
    
                        assistant_context=f"""
                        {json.dumps(pre_agentic_task_json_result.get("data"),indent=4)}
                        """
                        user_feedback_query=f"""
                        failed_at:{failed_at}
                        error_msg:{error_msg}
                        """
                        # RATE-LIMIT Consideration 
                        time.sleep(2)
                        typewrite("CONSIDERING LLM RATE LIMITS AND TRYING TO RESOLVE IN NEXT ITERATION.....", style="info", speed=0.08)

                        part_of_pre_agentic_task_json_result = adv1_usertojson(MY_MODEL, user_feedback_query, MY_KEY, common_uuid=common_uuid,system_prompt=SYSTEM_PROMPT,assistant_context=assistant_context,chat_history=chat_history,vector_store_ids=vector_store_ids,max_num_results=max_num_results,fullpower=fullpower,fullpower2X=fullpower2X,code_interpreter=code_interpreter,xsearch=xsearch,collections_search=collections_search,websearch=websearch,TOMLOBJ=TOMLOBJ)

                        successfully_created_prev_agentic_task_json = create_json_file(pre_agentic_task_json_result.get("data",{}), f"{agentic_task_jsonPath[:-5]}_{run_agentic_iteration_count}.json")
                        
                        # ADDIND FILES TO BE DELETED
                        
                        FILES_TO_DELETE.append(f"{agentic_task_jsonPath[:-5]}_{run_agentic_iteration_count}.json")
                        
                        for a_step,the_block_value in (part_of_pre_agentic_task_json_result.get("data",{}).get("Agentic_Data",{}).get("step",{})).items():
                           for a_sub_step,the_loc in the_block_value.items():
                                value_type=str(type(the_loc)).split("'")[1]
                                if value_type in ["list", "dict", "array", "obj"]:
                                    passing_value = json.dumps(the_loc)
                                else:
                                    passing_value = str(the_loc)
                                json_controller(further_file_path=f"{agentic_task_pre_str}_{common_uuid}.json",actionType="store",key=f"Agentic_Data.step.{a_step}.{a_sub_step}",defaultLoc=DefaultLoc,value=passing_value,valueType=value_type)
                                pre_agentic_task_json_result["data"]["Agentic_Data"]["step"][a_step][a_sub_step]=the_loc
                    else:
                        break
                            
                else:
                    break
        else:
            break
    # SAVE CONVERSATIONS TO CONVERSATION DB
    db_handler_obj = ALL_SQL_INTERACTIONS()
    db_handler_obj.add_conversation(topic_name=TOPIC_NAME,content=json.dumps(pre_agentic_task_json_result["data"]),is_bot=True,timestamp=datetime.now())
    # DELETE FILES AND FOLDER
    AutomaticFileToCollection.safe_delete_paths(paths_to_delete=FILES_TO_DELETE)

def main():
    DEFAULT_USER_QUERY="Hello, Introduce Yourself"
    parser = argparse.ArgumentParser(description="Hyejack-Powershell args.")
    parser.add_argument("--CREDENTIALS", action="store_true")
    parser.add_argument("--SIDEBAR", action="store_true")
    parser.add_argument("--HYE_JACK", action="store_true")
    parser.add_argument("--MAXCHATHISTORY", action="store_true")
    parser.add_argument("--MINCHATHISTORY", action="store_true")
    parser.add_argument("--AVGCHATHISTORY", action="store_true")
    parser.add_argument("--COLLECTIONREF", action="store_true")
    parser.add_argument("--COMPUTATIONALABILITY", action="store_true")
    parser.add_argument("--WEBSEARCH",action="store_true")
    parser.add_argument("--XSEARCH",action="store_true")
    parser.add_argument("--FULLPOWER",action="store_true")
    parser.add_argument("--FULLPOWER2X",action="store_true")
    parser.add_argument("--RETRIVALCOUNT", type=int,default=1)

    parser.add_argument("--TEST",action="store_true")

    parser.add_argument("message", nargs='?',default=DEFAULT_USER_QUERY)
    parser.add_argument("--DefaultLoc", default=".")
    parser.add_argument("--CONFIGURATIONFILE", default="./hyejack_powershell_configuration.toml")
    parser.add_argument("--TRYCOUNT", type=int,default=20)
    args = parser.parse_args()

    CONFIGURATION_TOML_OBJ=GrokKnowledgeBaseFileManager.read_toml_file(args.CONFIGURATIONFILE)

    # Get database connection from environment variables
    db_host = os.getenv('PG_HOST', 'localhost')
    db_name = os.getenv('PG_DB', 'poweragent_kb')
    db_user = os.getenv('PG_USER', 'poweradmin')
    db_password = os.getenv('PG_PASSWORD', 'StaticPassword123!')
    

    if(args.CREDENTIALS):
        # Create credential manager
        cred_manager = CredentialManager(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password
        )
        
        try:
            # Run interactive menu
            interactive_credential_menu(cred_manager)
        finally:
            # Close database connection
            cred_manager.close()
    elif(args.SIDEBAR):
        selected_topic = leaf_selected_topic()    
        
    elif(args.HYE_JACK):
        credential_manager_obj = CredentialManager(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password
        )
        credentials=credential_manager_obj.get_credential()
        if(credentials):
            if(not credentials.get("grok_api_key",None) or (not credentials.get("grok_management_key",None))):
                try:
                    interactive_credential_menu(credential_manager_obj)
                finally:
                    credential_manager_obj.close()

        credentials=credential_manager_obj.get_credential()
        if(credentials):
            if(credentials.get("grok_api_key",None) and (credentials.get("grok_management_key",None))):
                db_host = os.getenv('PG_HOST', 'localhost')
                db_name = os.getenv('PG_DB', 'poweragent_kb')
                db_user = os.getenv('PG_USER', 'poweradmin')
                db_password = os.getenv('PG_PASSWORD', 'StaticPassword123!')
            
                db_handler_obj = ALL_SQL_INTERACTIONS()
                current_topic=db_handler_obj.get_current_topic()
                current_topic_obj=db_handler_obj.get_topic_by_name(topic_name=current_topic)
                if (not current_topic):
                    current_topic = leaf_selected_topic()
                else:
                    topic_selected_print_console(current_topic)
                    if(args.message != DEFAULT_USER_QUERY):
                        user_chat_bubble(args.message,MSG_FROM=user_icon)
                        db_handler_obj.add_conversation(topic_name=current_topic,content=args.message,is_user=True,timestamp=datetime.now())
                        
                        prev_history_count=None
                        previous_conversational_list=[]
                        vector_store_ids=[]

                        collecchunking=args.RETRIVALCOUNT
                        if collecchunking>40:
                            collecchunking=40
                        elif collecchunking<0:
                            collecchunking=1

                        xsearch_bool=False
                        websearch_bool=False
                        computationability=False
                        collectionref=False
                        fullpower=False
                        fullpower2x=False
                        
                        # ||| TOOL SELECT |||

                        if args.FULLPOWER:
                            fullpower=True
                        elif args.FULLPOWER2X:
                            fullpower2x=True
                        else:
                            if (args.XSEARCH):
                                xsearch_bool=True
                            if (args.WEBSEARCH):
                                websearch_bool=True
                            if (args.COMPUTATIONALABILITY):
                                computationability=True

                        if (args.COLLECTIONREF or args.FULLPOWER or args.FULLPOWER2X):
                            collectionref=True
                            vector_store_ids.append(current_topic_obj.get("collection_id",None))
                        
                        # ||| PREVIOUS HISTORY COUNT TO SEND ||||
                        if(args.MINCHATHISTORY):
                            prev_history_count=5
                        elif(args.AVGCHATHISTORY):
                            prev_history_count=10
                        elif(args.MAXCHATHISTORY):
                            prev_history_count=20
                        # elif(args.EMBEDCHATHISTORY):
                        #     prev_history_count=20
                        if(prev_history_count):
                            previous_conversational_list=db_handler_obj.get_conversations_by_topic(topic_name=current_topic,limit=prev_history_count)
                            previous_conversational_list.reverse()
                            previous_conversational_list=previous_conversational_list[:-1]
                        # @get chat history here via accessing@ previous_conversational_list
                        hyjackPowershell(MY_KEY=credentials.get("grok_api_key",""),GROK_MANAGEMENT_KEY=credentials.get("grok_management_key",""),TOPIC_NAME=current_topic,Query=args.message,DefaultLoc=args.DefaultLoc,TRYCOUNT=args.TRYCOUNT,chat_history=previous_conversational_list,vector_store_ids=vector_store_ids,max_num_results= collecchunking,fullpower= fullpower,fullpower2X= fullpower2x,code_interpreter= computationability,xsearch= xsearch_bool,collections_search= collectionref,websearch= websearch_bool,TOMLOBJ=CONFIGURATION_TOML_OBJ,DBMANAGEROBJ=db_handler_obj)
                    else:
                        user_chat_bubble(user_content="Hello, I am Jack, your assistant",MSG_FROM=offline_jack_chat_buuble_icon)
        else:
            typewrite("Add Your Grok Credentails (Grok_LLM_API_KEY,GROK_MANAGEMENT_KEY) First...", style="danger", speed=0.02)
            typewrite("RUN: ' HyeJack-Powershell --CREDENTIALS ' for credential main menu. ", style="midnight", speed=0.02)

main()