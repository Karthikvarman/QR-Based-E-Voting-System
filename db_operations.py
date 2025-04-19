from db_config import db_manager
from typing import Optional, Dict, List
import hashlib
from datetime import date

class VotingDBOperations:
    """High-level operations for the voting system"""
    
    @staticmethod
    def generate_qr_data(aadhaar: str, password_hash: str) -> str:
        """Generate QR code data string"""
        return f"{aadhaar}:{password_hash}"

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def register_voter(self, aadhaar: str, name: str, dob: date, password: str) -> bool:
        """Register a new voter with the system"""
        password_hash = self.hash_password(password)
        qr_data = self.generate_qr_data(aadhaar, password_hash)
        
        return db_manager.register_voter(
            aadhaar=aadhaar,
            name=name,
            dob=dob.isoformat(),
            password_hash=password_hash,
            qr_code_data=qr_data
        )

    def authenticate_voter(self, qr_data: str) -> Optional[Dict]:
        """Authenticate voter using QR code data"""
        try:
            aadhaar, password_hash = qr_data.split(':')
            voter = db_manager.get_voter_by_aadhaar(aadhaar)
            
            if voter and voter['password_hash'] == password_hash:
                return voter
            return None
        except ValueError:
            return None

    def cast_vote(self, voter_id: int, candidate: str) -> bool:
        """Cast a vote if the voter hasn't already voted"""
        if db_manager.has_voted(voter_id):
            return False
        return db_manager.cast_vote(voter_id, candidate)

    def get_results(self) -> Dict[str, int]:
        """Get current election results"""
        return db_manager.get_election_results() or {}

    def get_voter_details(self, voter_id: int) -> Optional[Dict]:
        """Get voter details by ID"""
        query = "SELECT * FROM voters WHERE id = %s"
        result = db_manager.execute_query(query, (voter_id,), fetch=True)
        return result[0] if result else None

    def get_all_voters(self) -> List[Dict]:
        """Get list of all registered voters"""
        query = "SELECT id, aadhaar, name, dob FROM voters"
        return db_manager.execute_query(query, fetch=True) or []

    def get_vote_details(self) -> List[Dict]:
        """Get detailed voting information"""
        query = """
        SELECT v.id, v.aadhaar, v.name, vo.candidate, vo.voted_at
        FROM voters v
        LEFT JOIN votes vo ON v.id = vo.voter_id
        """
        return db_manager.execute_query(query, fetch=True) or []