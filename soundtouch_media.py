"""
SoundTouch Media Server Integration
Supports SMB/CIFS shares, NFS, and local file streaming.
"""

import os
from typing import List, Dict, Optional
from pathlib import Path
import mimetypes


class MediaServer:
    """Base class for media server implementations."""
    
    def __init__(self, name: str, host: str, share: str = "", username: str = "", password: str = ""):
        self.name = name
        self.host = host
        self.share = share
        self.username = username
        self.password = password
    
    def connect(self) -> bool:
        """Connect to the media server."""
        raise NotImplementedError
    
    def disconnect(self):
        """Disconnect from the media server."""
        raise NotImplementedError
    
    def list_files(self, path: str = "/", extensions: List[str] = None) -> List[Dict]:
        """List files in the given path."""
        raise NotImplementedError
    
    def get_file_url(self, file_path: str) -> str:
        """Get HTTP URL for streaming a file."""
        raise NotImplementedError


class SMBMediaServer(MediaServer):
    """SMB/CIFS network share support."""
    
    def __init__(self, name: str, host: str, share: str, username: str = "", password: str = ""):
        super().__init__(name, host, share, username, password)
        self.conn = None
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to SMB share."""
        try:
            from smb.SMBConnection import SMBConnection
            
            # Parse host (might include domain)
            parts = self.username.split('\\') if '\\' in self.username else [self.username]
            domain = parts[0] if len(parts) > 1 else ''
            user = parts[1] if len(parts) > 1 else parts[0]
            
            self.conn = SMBConnection(
                user,
                self.password,
                'SoundTouchAPI',
                self.host,
                domain=domain,
                use_ntlm_v2=True,
                is_direct_tcp=True
            )
            
            self._connected = self.conn.connect(self.host, 445)
            return self._connected
        except Exception as e:
            print(f"SMB connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from SMB share."""
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
        self._connected = False
    
    def list_files(self, path: str = "/", extensions: List[str] = None) -> List[Dict]:
        """List media files from SMB share."""
        if not self._connected:
            if not self.connect():
                return []
        
        if extensions is None:
            extensions = ['.mp3', '.m4a', '.flac', '.wav', '.ogg', '.mp4', '.mkv', '.avi']
        
        files = []
        try:
            # Clean path
            path = path.replace('\\', '/').strip('/')
            
            # List directory
            from smb.smb_structs import OperationFailure
            try:
                shared_files = self.conn.listPath(self.share, path if path else '/')
            except OperationFailure:
                return []
            
            for f in shared_files:
                if f.filename in ['.', '..']:
                    continue
                
                file_path = f"{path}/{f.filename}" if path else f.filename
                
                if f.isDirectory:
                    # Recursively list subdirectories
                    files.extend(self.list_files(file_path, extensions))
                else:
                    # Check extension
                    ext = os.path.splitext(f.filename)[1].lower()
                    if ext in extensions:
                        files.append({
                            'name': f.filename,
                            'path': file_path,
                            'size': f.file_size,
                            'type': self._get_media_type(ext),
                            'server': self.name
                        })
        except Exception as e:
            print(f"Error listing files: {e}")
        
        return files
    
    def get_file_url(self, file_path: str) -> str:
        """Return a local streaming URL (will be handled by API endpoint)."""
        # Encode path for URL
        from urllib.parse import quote
        return f"/api/media/stream/{self.name}/{quote(file_path)}"
    
    def read_file(self, file_path: str, offset: int = 0, length: int = None):
        """Read file content for streaming."""
        if not self._connected:
            if not self.connect():
                return None
        
        try:
            file_obj = BytesIOWrapper()
            self.conn.retrieveFile(self.share, file_path, file_obj)
            file_obj.seek(offset)
            
            if length:
                return file_obj.read(length)
            return file_obj.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return None
    
    @staticmethod
    def _get_media_type(ext: str) -> str:
        """Get media type from extension."""
        audio_exts = ['.mp3', '.m4a', '.flac', '.wav', '.ogg', '.aac']
        video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.webm']
        
        if ext in audio_exts:
            return 'audio'
        elif ext in video_exts:
            return 'video'
        return 'unknown'


class LocalMediaServer(MediaServer):
    """Local filesystem media server."""
    
    def __init__(self, name: str, path: str):
        super().__init__(name, 'localhost', path)
        self.root_path = Path(path)
    
    def connect(self) -> bool:
        """Check if path exists."""
        return self.root_path.exists() and self.root_path.is_dir()
    
    def disconnect(self):
        """Nothing to disconnect for local files."""
        pass
    
    def list_files(self, path: str = "", extensions: List[str] = None) -> List[Dict]:
        """List local media files."""
        if extensions is None:
            extensions = ['.mp3', '.m4a', '.flac', '.wav', '.ogg', '.mp4', '.mkv', '.avi']
        
        files = []
        search_path = self.root_path / path if path else self.root_path
        
        if not search_path.exists():
            return []
        
        try:
            for item in search_path.rglob('*'):
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext in extensions:
                        rel_path = item.relative_to(self.root_path)
                        files.append({
                            'name': item.name,
                            'path': str(rel_path).replace('\\', '/'),
                            'size': item.stat().st_size,
                            'type': self._get_media_type(ext),
                            'server': self.name
                        })
        except Exception as e:
            print(f"Error listing local files: {e}")
        
        return files
    
    def get_file_url(self, file_path: str) -> str:
        """Return a local streaming URL."""
        from urllib.parse import quote
        return f"/api/media/stream/{self.name}/{quote(file_path)}"
    
    def get_file_path(self, file_path: str) -> Path:
        """Get absolute file path."""
        return self.root_path / file_path
    
    @staticmethod
    def _get_media_type(ext: str) -> str:
        """Get media type from extension."""
        audio_exts = ['.mp3', '.m4a', '.flac', '.wav', '.ogg', '.aac']
        video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.webm']
        
        if ext in audio_exts:
            return 'audio'
        elif ext in video_exts:
            return 'video'
        return 'unknown'


class BytesIOWrapper:
    """Wrapper for SMB file retrieval."""
    def __init__(self):
        from io import BytesIO
        self.buffer = BytesIO()
    
    def write(self, data):
        return self.buffer.write(data)
    
    def read(self, size=-1):
        return self.buffer.read(size)
    
    def seek(self, pos):
        return self.buffer.seek(pos)
    
    def tell(self):
        return self.buffer.tell()


class MediaServerManager:
    """Manages multiple media servers."""
    
    def __init__(self):
        self.servers: Dict[str, MediaServer] = {}
    
    def add_server(self, server: MediaServer):
        """Add a media server."""
        self.servers[server.name] = server
    
    def remove_server(self, name: str):
        """Remove a media server."""
        if name in self.servers:
            self.servers[name].disconnect()
            del self.servers[name]
    
    def get_server(self, name: str) -> Optional[MediaServer]:
        """Get a media server by name."""
        return self.servers.get(name)
    
    def list_servers(self) -> List[Dict]:
        """List all configured servers."""
        return [
            {
                'name': name,
                'type': 'SMB' if isinstance(server, SMBMediaServer) else 'Local',
                'host': server.host,
                'share': server.share if hasattr(server, 'share') else ''
            }
            for name, server in self.servers.items()
        ]
    
    def search_all(self, extensions: List[str] = None) -> List[Dict]:
        """Search all servers for media files."""
        all_files = []
        for server in self.servers.values():
            if server.connect():
                files = server.list_files(extensions=extensions)
                all_files.extend(files)
                server.disconnect()
        return all_files


# Global manager instance
media_manager = MediaServerManager()
