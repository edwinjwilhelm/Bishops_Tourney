"""
WebSocket Move Validation Module
Validates all game moves server-side to prevent cheating
"""

from typing import Dict, Any, Optional, List
import json


class MoveValidator:
    """Validates game moves server-side"""
    
    def __init__(self, engine):
        """
        Args:
            engine: Bishops game engine instance
        """
        self.engine = engine
        self.game_states: Dict[str, Dict[str, Any]] = {}  # room_id -> state
    
    def initialize_game(self, room_id: str, num_players: int = 2):
        """Initialize game state for a room"""
        self.game_states[room_id] = {
            'current_turn': 'WHITE',
            'seats_taken': {},
            'move_history': [],
            'game_over': False,
            'num_players': num_players
        }
    
    def validate_seat_action(
        self, 
        room_id: str, 
        user_id: str, 
        seat: str, 
        action: str
    ) -> tuple[bool, str]:
        """
        Validate seat join/quit actions
        
        Args:
            room_id: Room identifier
            user_id: User identifier
            seat: Seat color (WHITE, GREY, BLACK, PINK)
            action: 'join' or 'quit'
        
        Returns:
            (is_valid, error_message)
        """
        if room_id not in self.game_states:
            return False, "Room not initialized"
        
        state = self.game_states[room_id]
        
        if action == 'join':
            # Check if seat already taken
            if seat in state['seats_taken']:
                existing_user = state['seats_taken'][seat]
                if existing_user != user_id:
                    return False, f"Seat {seat} already taken by {existing_user}"
            
            # Check if user already in another seat
            for s, u in state['seats_taken'].items():
                if u == user_id and s != seat:
                    return False, f"User already in seat {s}"
            
            state['seats_taken'][seat] = user_id
            return True, ""
        
        elif action == 'quit':
            # Check if user actually in this seat
            if seat not in state['seats_taken']:
                return False, f"Seat {seat} is not taken"
            
            if state['seats_taken'][seat] != user_id:
                return False, f"User not in seat {seat}"
            
            del state['seats_taken'][seat]
            return True, ""
        
        return False, f"Invalid action: {action}"
    
    def validate_move(
        self,
        room_id: str,
        user_id: str,
        move_data: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Validate a game move
        
        Args:
            room_id: Room identifier
            user_id: User making the move
            move_data: Move information (from, to, piece, etc.)
        
        Returns:
            (is_valid, error_message)
        """
        if room_id not in self.game_states:
            return False, "Room not initialized"
        
        state = self.game_states[room_id]
        
        # Check if game is over
        if state['game_over']:
            return False, "Game is over"
        
        # Determine which seat this user is in
        user_seat = None
        for seat, uid in state['seats_taken'].items():
            if uid == user_id:
                user_seat = seat
                break
        
        if not user_seat:
            return False, "User not seated in game"
        
        # Check if it's this player's turn
        current_turn = state['current_turn']
        if user_seat != current_turn:
            return False, f"Not your turn (current: {current_turn})"
        
        # Validate move with engine
        # This depends on your engine's API - adjust as needed
        try:
            from_pos = move_data.get('from')
            to_pos = move_data.get('to')
            
            if not from_pos or not to_pos:
                return False, "Invalid move format"
            
            # Check if move is legal using engine
            legal_moves = self._get_legal_moves(room_id, user_seat)
            move_str = f"{from_pos}-{to_pos}"
            
            if move_str not in legal_moves:
                return False, f"Illegal move: {move_str}"
            
            # Record move
            state['move_history'].append({
                'seat': user_seat,
                'move': move_data,
                'timestamp': self._get_timestamp()
            })
            
            # Update turn
            self._advance_turn(room_id)
            
            return True, ""
        
        except Exception as e:
            return False, f"Move validation error: {str(e)}"
    
    def _get_legal_moves(self, room_id: str, seat: str) -> List[str]:
        """
        Get legal moves for a seat using the engine
        
        This is a placeholder - integrate with your actual engine API
        """
        # TODO: Call your Bishops_Golden.py engine to get legal moves
        # Example: return self.engine.get_legal_moves(seat)
        return []  # Placeholder
    
    def _advance_turn(self, room_id: str):
        """Advance to next player's turn"""
        state = self.game_states[room_id]
        seats_order = ['WHITE', 'GREY', 'BLACK', 'PINK']
        
        # Get active seats
        active_seats = [s for s in seats_order if s in state['seats_taken']]
        
        if not active_seats:
            return
        
        # Find current seat index
        try:
            current_idx = active_seats.index(state['current_turn'])
            next_idx = (current_idx + 1) % len(active_seats)
            state['current_turn'] = active_seats[next_idx]
        except (ValueError, IndexError):
            # Fallback to first active seat
            state['current_turn'] = active_seats[0] if active_seats else 'WHITE'
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def validate_ai_toggle(
        self,
        room_id: str,
        user_id: str,
        seat: str,
        enable: bool
    ) -> tuple[bool, str]:
        """
        Validate AI enable/disable action
        
        Args:
            room_id: Room identifier
            user_id: User requesting action
            seat: Seat to toggle AI
            enable: True to enable, False to disable
        
        Returns:
            (is_valid, error_message)
        """
        if room_id not in self.game_states:
            return False, "Room not initialized"
        
        state = self.game_states[room_id]
        
        # Check if user has permission (either in the seat or admin)
        user_seat = state['seats_taken'].get(seat)
        
        # For now, allow any seated user to toggle AI
        # You can make this more restrictive
        is_seated = user_id in state['seats_taken'].values()
        
        if not is_seated:
            return False, "Must be seated to toggle AI"
        
        return True, ""
    
    def validate_mode_change(
        self,
        room_id: str,
        user_id: str,
        new_mode: str
    ) -> tuple[bool, str]:
        """
        Validate game mode change
        
        Args:
            room_id: Room identifier
            user_id: User requesting change
            new_mode: New game mode
        
        Returns:
            (is_valid, error_message)
        """
        if room_id not in self.game_states:
            return False, "Room not initialized"
        
        state = self.game_states[room_id]
        
        # Only allow mode change if user is seated
        if user_id not in state['seats_taken'].values():
            return False, "Must be seated to change mode"
        
        # Validate mode value
        valid_modes = ['classic', '4player', 'custom']  # Adjust based on your modes
        if new_mode not in valid_modes:
            return False, f"Invalid mode: {new_mode}"
        
        return True, ""
    
    def get_game_state(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get current game state for a room"""
        return self.game_states.get(room_id)
    
    def remove_room(self, room_id: str):
        """Clean up game state when room is deleted"""
        if room_id in self.game_states:
            del self.game_states[room_id]


# =============================================================================
# WEBSOCKET MESSAGE VALIDATION
# =============================================================================

def validate_websocket_message(
    message: Dict[str, Any],
    user_id: str,
    validator: MoveValidator,
    room_id: str
) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validate WebSocket message from client
    
    Args:
        message: Raw message from client
        user_id: User sending message
        validator: MoveValidator instance
        room_id: Current room
    
    Returns:
        (is_valid, error_message, sanitized_message)
    """
    msg_type = message.get('type')
    
    if not msg_type:
        return False, "Missing message type", None
    
    # Validate based on message type
    if msg_type == 'move':
        is_valid, error = validator.validate_move(
            room_id,
            user_id,
            message.get('data', {})
        )
        if not is_valid:
            return False, error, None
        return True, "", message
    
    elif msg_type == 'join_seat':
        seat = message.get('seat')
        is_valid, error = validator.validate_seat_action(
            room_id,
            user_id,
            seat,
            'join'
        )
        if not is_valid:
            return False, error, None
        return True, "", message
    
    elif msg_type == 'quit_seat':
        seat = message.get('seat')
        is_valid, error = validator.validate_seat_action(
            room_id,
            user_id,
            seat,
            'quit'
        )
        if not is_valid:
            return False, error, None
        return True, "", message
    
    elif msg_type == 'toggle_ai':
        seat = message.get('seat')
        enable = message.get('enable', True)
        is_valid, error = validator.validate_ai_toggle(
            room_id,
            user_id,
            seat,
            enable
        )
        if not is_valid:
            return False, error, None
        return True, "", message
    
    elif msg_type == 'set_mode':
        mode = message.get('mode')
        is_valid, error = validator.validate_mode_change(
            room_id,
            user_id,
            mode
        )
        if not is_valid:
            return False, error, None
        return True, "", message
    
    elif msg_type == 'chat':
        # Sanitize chat messages
        from .security import InputSanitizer
        text = message.get('text', '')
        sanitized = InputSanitizer.sanitize_string(text, max_length=500)
        
        if InputSanitizer.is_suspicious(text):
            return False, "Suspicious content detected", None
        
        message['text'] = sanitized
        return True, "", message
    
    # Allow other message types for now (can restrict later)
    return True, "", message
