
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Testing RAG module imports...")
try:
    from services import intent_router
    print("✓ services.intent_router imported successfully!")
except Exception as e:
    print(f"✗ Error importing services.intent_router: {e}")
    sys.exit(1)

try:
    from services import rag_service
    print("✓ services.rag_service imported successfully!")
except Exception as e:
    print(f"✗ Error importing services.rag_service: {e}")
    sys.exit(1)

try:
    from agents import orchestrator
    print("✓ agents.orchestrator imported successfully!")
except Exception as e:
    print(f"✗ Error importing agents.orchestrator: {e}")
    sys.exit(1)

print("\n✅ All RAG-related modules are importable!")
