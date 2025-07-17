#!/usr/bin/env python3
"""
Test retrieving all memories for a specific user ID
"""

import asyncio
import os

async def test_retrieve_memories():
    """Test retrieving memories for our user"""
    try:
        import vertexai
        
        project = 'gen-lang-client-0220754900'
        location = 'us-central1'
        
        print("🔍 TESTING MEMORY RETRIEVAL")
        print("="*50)
        
        # Initialize
        vertexai.init(project=project, location=location)
        client = vertexai.Client(project=project, location=location)
        
        # Get agent engine
        agent_engines = list(client.agent_engines.list())
        agent_engine = agent_engines[0]
        agent_engine_id = agent_engine.api_resource.name.split('/')[-1]
        
        print(f"🏗️ Agent Engine ID: {agent_engine_id}")
        print(f"🏗️ Agent Engine Name: {agent_engine.api_resource.name}")
        print()
        
        # Test user IDs from our session mapping
        test_user_ids = [
            "9524689c-c3eb-43be-965c-c06f87702219",  # The one we just added data to
            "10ff430e-d3ed-4cc6-ac88-401b3a8ff153",
            "f23f0dff-2c43-4dee-8bce-f42c0532c295",
            "fbe05a8f-fb44-4608-9f8d-f176f369533c"
        ]
        
        for user_id in test_user_ids:
            print(f"👤 Testing user: {user_id}")
            
            try:
                # Retrieve all memories for this user
                retrieved_memories = list(
                    client.agent_engines.retrieve_memories(
                        name=agent_engine.api_resource.name,
                        scope={"user_id": user_id}
                    )
                )
                
                print(f"📊 Found {len(retrieved_memories)} memories for user {user_id}")
                
                if retrieved_memories:
                    for i, memory_item in enumerate(retrieved_memories):
                        print(f"💭 Memory {i+1}:")
                        print(f"   Fact: {memory_item.memory.fact}")
                        print(f"   Available attributes: {dir(memory_item)}")
                        if hasattr(memory_item, 'context'):
                            print(f"   Context: {memory_item.context}")
                        print()
                else:
                    print("   💭 No memories found")
                    
            except Exception as e:
                print(f"❌ Failed to retrieve memories for {user_id}: {e}")
            
            print("-" * 30)
            print()
        
        # Also test with no scope (retrieve all memories)
        print("🌍 Testing retrieval with NO SCOPE (all memories):")
        try:
            all_memories = list(
                client.agent_engines.retrieve_memories(
                    name=agent_engine.api_resource.name
                )
            )
            print(f"📊 Found {len(all_memories)} total memories across all users")
            
            if all_memories:
                for i, memory_item in enumerate(all_memories):
                    print(f"💭 Memory {i+1}:")
                    print(f"   Fact: {memory_item.memory.fact}")
                    print(f"   Scope: {memory_item.scope}")
                    print()
            
        except Exception as e:
            print(f"❌ Failed to retrieve all memories: {e}")
        
        print("="*50)
        print("🎯 CONCLUSION:")
        print("="*50)
        print("If memories are found → Memory Bank is working and accumulating data")
        print("If no memories found → Either processing time needed or insufficient content")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_retrieve_memories())