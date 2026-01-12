"""
NowPlayingStatus model - parses now_playing endpoint response.
"""
import xml.etree.ElementTree as ET
from typing import Optional


class NowPlayingStatus:
    """
    Represents the current playback status of a SoundTouch device.
    Parses the /now_playing endpoint XML response.
    """
    
    def __init__(self, root: ET.Element = None, **kwargs):
        """
        Initialize from XML Element or from kwargs.
        
        Args:
            root: XML Element from /now_playing response
            **kwargs: Individual properties (source, track, artist, album, duration, position, playStatus)
        """
        self._source = None
        self._source_account = None
        self._track = None
        self._artist = None
        self._album = None
        self._duration = 0  # milliseconds
        self._position = 0  # milliseconds
        self._play_status = None
        self._art_url = None
        self._station_name = None
        self._genre = None
        self._duration_fallback = None  # Fallback duration from external source
        
        if root is not None:
            self._parse_xml(root)
        else:
            # Initialize from kwargs
            self._source = kwargs.get('source', 'Unknown')
            self._source_account = kwargs.get('sourceAccount', '')
            self._track = kwargs.get('track', 'Unknown')
            self._artist = kwargs.get('artist', 'Unknown')
            self._album = kwargs.get('album', 'Unknown')
            self._duration = kwargs.get('duration', 0)
            self._position = kwargs.get('position', 0)
            self._play_status = kwargs.get('playStatus', 'UNKNOWN')
            self._art_url = kwargs.get('artUrl')
            self._station_name = kwargs.get('stationName')
            self._genre = kwargs.get('genre')
    
    def set_duration_fallback(self, duration_ms: int):
        """Set fallback duration (e.g., from file metadata) if device doesn't provide it."""
        self._duration_fallback = duration_ms
    
    def _parse_xml(self, root: ET.Element):
        """Parse XML from now_playing endpoint."""
        # Attributes
        self._source = root.get('source', 'Unknown')
        self._source_account = root.get('sourceAccount', '')
        
        # playStatus can be either an attribute OR a child element
        self._play_status = root.get('playStatus') or root.findtext('playStatus', 'UNKNOWN')
        
        # Text elements
        self._track = root.findtext('track', 'Unknown')
        self._artist = root.findtext('artist', 'Unknown')
        self._album = root.findtext('album', 'Unknown')
        self._genre = root.findtext('genre')
        self._station_name = root.findtext('stationName')
        
        # Art
        art_elem = root.find('art')
        if art_elem is not None:
            self._art_url = art_elem.text
        
        # Time (duration and position)
        # Expected format: <time total="265">15</time>
        # But some sources might only have text without total attribute
        time_elem = root.find('time')
        if time_elem is not None:
            try:
                # Try to get total attribute (milliseconds)
                total_str = time_elem.get('total')
                if total_str:
                    self._duration = int(total_str)
                else:
                    self._duration = 0
                
                # Position is in the text (milliseconds)
                self._position = int(time_elem.text or 0)
                
                # Debug: log what we got
                if not total_str:
                    print(f"[DEBUG] <time> element has no 'total' attr. Attrs: {time_elem.attrib}, Text: {time_elem.text}")
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Error parsing <time>: {e}, Attrs: {time_elem.attrib}, Text: {time_elem.text}")
                self._duration = 0
                self._position = 0
    
    @property
    def source(self) -> str:
        """The media source (e.g., 'UPNP', 'BLUETOOTH', 'PANDORA')."""
        return self._source
    
    @property
    def source_account(self) -> str:
        """Source account (e.g., DLNA UUID)."""
        return self._source_account
    
    @property
    def track(self) -> str:
        """Current track name."""
        return self._track
    
    @property
    def artist(self) -> str:
        """Artist name."""
        return self._artist
    
    @property
    def album(self) -> str:
        """Album name."""
        return self._album
    
    @property
    def duration(self) -> int:
        """Track duration in milliseconds. Returns fallback if device doesn't provide it."""
        if self._duration > 0:
            return self._duration
        # Device didn't report duration (common for streaming sources)
        # Use fallback if available
        if self._duration_fallback and self._duration_fallback > 0:
            return self._duration_fallback
        return 0
    
    @property
    def position(self) -> int:
        """Current playback position in milliseconds."""
        return self._position
    
    @property
    def play_status(self) -> str:
        """Playback status (e.g., 'PLAY_STATE', 'PAUSE_STATE', 'STOP_STATE')."""
        return self._play_status
    
    @property
    def is_playing(self) -> bool:
        """True if currently playing."""
        return self._play_status == 'PLAY_STATE'
    
    @property
    def is_paused(self) -> bool:
        """True if paused."""
        return self._play_status == 'PAUSE_STATE'
    
    @property
    def is_stopped(self) -> bool:
        """True if stopped."""
        return self._play_status == 'STOP_STATE'
    
    @property
    def art_url(self) -> Optional[str]:
        """Art image URL."""
        return self._art_url
    
    @property
    def station_name(self) -> Optional[str]:
        """Station name (for radio sources)."""
        return self._station_name
    
    @property
    def genre(self) -> Optional[str]:
        """Genre of the track."""
        return self._genre
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'source': self._source,
            'sourceAccount': self._source_account,
            'track': self._track,
            'artist': self._artist,
            'album': self._album,
            'duration': self._duration,
            'position': self._position,
            'playStatus': self._play_status,
            'artUrl': self._art_url,
            'stationName': self._station_name,
            'genre': self._genre,
        }
    
    def __repr__(self) -> str:
        return f"NowPlayingStatus({self._artist} - {self._track} [{self._position}ms/{self._duration}ms] {self._play_status})"
