#!/usr/bin/env python3
"""
Simple test of Google Memory Bank concept using just Gemini API
This doesn't use the full Memory Bank service, but simulates the concept
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import google.generativeai as genai
    
    # Configure Gemini
    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("No Google API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in .env")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
except ImportError:
    print("google-generativeai not installed. Run: pip install google-generativeai")
    exit(1)

class SimpleMemoryBank:
    """Simple in-memory simulation of Memory Bank functionality"""
    
    def __init__(self):
        self.memories: Dict[str, List[Dict[str, Any]]] = {}
        self.sessions: Dict[str, List[Dict[str, Any]]] = {}
    
    def add_session_message(self, user_id: str, session_id: str, role: str, content: str):
        """Add a message to session history"""
        if user_id not in self.sessions:
            self.sessions[user_id] = []
        
        self.sessions[user_id].append({
            'session_id': session_id,
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def extract_memories(self, user_id: str, session_id: str):
        """Extract memories from session using Gemini"""
        if user_id not in self.sessions:
            return []
        
        # Get session messages
        session_messages = [
            msg for msg in self.sessions[user_id] 
            if msg['session_id'] == session_id
        ]
        
        if not session_messages:
            return []
        
        # Create conversation context
        conversation = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in session_messages
        ])
        
        # Use Gemini to extract key facts/preferences
        extraction_prompt = f"""
        Analyze this conversation and extract key facts, preferences, and important information about the user.
        Focus on:
        - Personal preferences
        - Important facts about the user
        - Context that would be useful to remember in future conversations
        
        Conversation:
        {conversation}
        
        Return the extracted information as a JSON list of memory objects, each with:
        - "fact": the specific fact or preference
        - "context": brief context about when/how this was mentioned
        - "importance": score 1-10 of how important this is to remember
        
        Return only valid JSON, no other text.
        """
        
        try:
            response = model.generate_content(extraction_prompt)
            memories_text = response.text.strip()
            
            # Try to parse as JSON
            if memories_text.startswith('```json'):
                memories_text = memories_text.replace('```json', '').replace('```', '').strip()
            
            extracted_memories = json.loads(memories_text)
            
            # Store memories
            if user_id not in self.memories:
                self.memories[user_id] = []
            
            for memory in extracted_memories:
                memory['session_id'] = session_id
                memory['extracted_at'] = datetime.now().isoformat()
                self.memories[user_id].append(memory)
            
            return extracted_memories
            
        except Exception as e:
            print(f"Error extracting memories: {e}")
            return []
    
    def search_memories(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """Search memories using Gemini for relevance"""
        if user_id not in self.memories:
            return []
        
        user_memories = self.memories[user_id]
        if not user_memories:
            return []
        
        # Use Gemini to find relevant memories
        search_prompt = f"""
        Given this query: "{query}"
        
        Find the most relevant memories from this list:
        {json.dumps(user_memories, indent=2)}
        
        Return a JSON list of the most relevant memories (max 5), ordered by relevance.
        Include the original memory objects with an additional "relevance_score" field (1-10).
        
        Return only valid JSON, no other text.
        """
        
        try:
            response = model.generate_content(search_prompt)
            results_text = response.text.strip()
            
            if results_text.startswith('```json'):
                results_text = results_text.replace('```json', '').replace('```', '').strip()
            
            relevant_memories = json.loads(results_text)
            return relevant_memories
            
        except Exception as e:
            print(f"Error searching memories: {e}")
            return user_memories[:3]  # Fallback to first 3 memories
    
    def get_memory_summary(self, user_id: str) -> str:
        """Get a summary of all memories for a user"""
        if user_id not in self.memories:
            return "No memories found for this user."
        
        memories = self.memories[user_id]
        if not memories:
            return "No memories found for this user."
        
        memory_facts = [memory['fact'] for memory in memories]
        return f"User has {len(memories)} stored memories:\n" + "\n".join(f"- {fact}" for fact in memory_facts)

def test_memory_bank():
    """Test the simple memory bank functionality"""
    print("🧠 Testing Simple Memory Bank with Gemini...")
    
    memory_bank = SimpleMemoryBank()
    user_id = "test_user_123"
    
    # Simulate a conversation session
    print("\n📝 Session 1: User shares preferences...")
    session1 = "session_001"
    
    # Add conversation messages
    memory_bank.add_session_message(user_id, session1, "user", "Hi! I'm working on toolstac.com - a Next.js project with Redis and AI agents.")
    memory_bank.add_session_message(user_id, session1, "assistant", "Great! I can help with your toolstac.com project. It sounds like a sophisticated setup with Next.js and Redis.")
    memory_bank.add_session_message(user_id, session1, "user", "I prefer TypeScript strict mode and always use environment variables for configuration.")
    memory_bank.add_session_message(user_id, session1, "assistant", "Noted! I'll ensure we use TypeScript strict mode and environment variables for all configuration.")
    
    # Extract memories from session
    print("🔍 Extracting memories from session...")
    extracted = memory_bank.extract_memories(user_id, session1)
    print(f"Extracted {len(extracted)} memories:")
    for memory in extracted:
        print(f"  - {memory.get('fact', 'Unknown fact')} (importance: {memory.get('importance', 'N/A')})")
    
    # Test memory search
    print("\n🔎 Searching memories...")
    
    queries = [
        "What does the user prefer for flights?",
        "Tell me about food preferences",
        "What's the user's name?"
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        results = memory_bank.search_memories(user_id, query)
        print(f"Found {len(results)} relevant memories:")
        for result in results:
            print(f"  - {result.get('fact', 'Unknown')} (relevance: {result.get('relevance_score', 'N/A')})")
    
    # Test new session with memory retrieval
    print("\n📝 Session 2: Using stored memories...")
    session2 = "session_002"
    
    # Simulate agent using memories to provide personalized response
    flight_memories = memory_bank.search_memories(user_id, "flight preferences")
    
    print("Agent retrieving memories for flight booking...")
    if flight_memories:
        print(f"Found relevant memory: {flight_memories[0].get('fact', 'Unknown')}")
        response = "Based on your preferences, I'll look for aisle seats for your flight."
    else:
        response = "I don't have any flight preferences stored. What would you prefer?"
    
    print(f"Agent response: {response}")
    
    # Show memory summary
    print(f"\n📊 Memory Summary:")
    print(memory_bank.get_memory_summary(user_id))
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_memory_bank()