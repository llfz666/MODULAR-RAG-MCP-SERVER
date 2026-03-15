"""Video Subtitle Loader and Audio Transcription.

This module implements video/audio file processing with:
1. Subtitle Extraction - Extract embedded subtitles from video files
2. Audio Transcription - Use Whisper for speech-to-text
3. Semantic Segmentation - Split transcript by semantic meaning
4. Multi-language Support - Support for multiple subtitle formats

Key Features:
- Extracts SRT, VTT, ASS subtitles from video files
- Uses Whisper for audio transcription when no subtitles exist
- Segments long transcripts by semantic meaning
- Preserves timestamps for reference
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SubtitleSegment:
    """Represents a subtitle segment."""
    index: int
    start_time: str  # HH:MM:SS,mmm format
    end_time: str
    text: str
    start_seconds: float = 0.0
    end_seconds: float = 0.0


class SubtitleExtractor:
    """Extract subtitles from video files."""
    
    # Common subtitle formats
    SUBTITLE_EXTENSIONS = {'.srt', '.vtt', '.ass', '.ssa', '.sub', '.idx'}
    
    def __init__(self):
        """Initialize subtitle extractor."""
        self._ffmpeg_available = self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @property
    def ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available."""
        return self._ffmpeg_available
    
    def extract_subtitles(
        self, 
        video_path: str | Path,
        output_dir: Optional[str | Path] = None,
        language: str = 'chi'
    ) -> List[SubtitleSegment]:
        """Extract subtitles from video file.
        
        Args:
            video_path: Path to video file.
            output_dir: Directory for extracted subtitles.
            language: Subtitle language preference.
            
        Returns:
            List of subtitle segments.
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not self._ffmpeg_available:
            logger.warning("ffmpeg not available, subtitle extraction disabled")
            return []
        
        # Create temp directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Try to extract subtitles
            subtitle_file = temp_path / f"extracted.srt"
            
            cmd = [
                'ffmpeg', '-i', str(video_path),
                '-map', '0:s:0',  # First subtitle stream
                '-c:s', 'srt',
                str(subtitle_file)
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=60
                )
                
                if result.returncode == 0 and subtitle_file.exists():
                    # Parse SRT file
                    return self._parse_srt(subtitle_file)
                
            except Exception as e:
                logger.warning(f"Subtitle extraction failed: {e}")
        
        # Fallback: try to find external subtitle file
        external_sub = self._find_external_subtitle(video_path)
        if external_sub:
            return self._parse_subtitle_file(external_sub)
        
        return []
    
    def _find_external_subtitle(
        self, 
        video_path: Path
    ) -> Optional[Path]:
        """Find external subtitle file matching video name."""
        video_dir = video_path.parent
        video_name = video_path.stem
        
        # Common subtitle naming patterns
        patterns = [
            f"{video_name}.srt",
            f"{video_name}.zh.srt",
            f"{video_name}.chs.srt",
            f"{video_name}.chi.srt",
            f"{video_name}.vtt",
        ]
        
        for pattern in patterns:
            subtitle_file = video_dir / pattern
            if subtitle_file.exists():
                return subtitle_file
        
        return None
    
    def _parse_subtitle_file(
        self, 
        subtitle_file: Path
    ) -> List[SubtitleSegment]:
        """Parse subtitle file based on extension."""
        ext = subtitle_file.suffix.lower()
        
        if ext == '.srt':
            return self._parse_srt(subtitle_file)
        elif ext == '.vtt':
            return self._parse_vtt(subtitle_file)
        elif ext in ('.ass', '.ssa'):
            return self._parse_ass(subtitle_file)
        
        return []
    
    def _parse_srt(self, srt_file: Path) -> List[SubtitleSegment]:
        """Parse SRT subtitle file.
        
        SRT format:
        1
        00:00:01,000 --> 00:00:04,000
        Hello, world!
        """
        segments = []
        
        with open(srt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by blank lines
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            try:
                index = int(lines[0].strip())
                
                # Parse timestamp line
                timestamp_match = re.match(
                    r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})',
                    lines[1]
                )
                
                if not timestamp_match:
                    continue
                
                start_time = timestamp_match.group(1).replace(',', '.')
                end_time = timestamp_match.group(2).replace(',', '.')
                
                # Text is remaining lines
                text = '\n'.join(lines[2:]).strip()
                
                # Convert to seconds
                start_seconds = self._time_to_seconds(start_time)
                end_seconds = self._time_to_seconds(end_time)
                
                segments.append(SubtitleSegment(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=text,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds
                ))
                
            except Exception as e:
                logger.debug(f"Failed to parse SRT block: {e}")
        
        return segments
    
    def _parse_vtt(self, vtt_file: Path) -> List[SubtitleSegment]:
        """Parse WebVTT subtitle file."""
        segments = []
        
        with open(vtt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip WEBVTT header
        content = re.sub(r'^WEBVTT.*?\n\n', '', content, flags=re.DOTALL)
        
        # Parse similar to SRT
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 2:
                continue
            
            try:
                # VTT format: timestamp line first
                timestamp_match = re.match(
                    r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})',
                    lines[0]
                )
                
                if not timestamp_match:
                    # Try without milliseconds
                    timestamp_match = re.match(
                        r'(\d{2}:\d{2}:\d{2})\s*-->\s*(\d{2}:\d{2}:\d{2})',
                        lines[0]
                    )
                
                if not timestamp_match:
                    continue
                
                start_time = timestamp_match.group(1)
                end_time = timestamp_match.group(2)
                
                # Text is remaining lines
                text = '\n'.join(lines[1:]).strip()
                
                start_seconds = self._time_to_seconds(start_time)
                end_seconds = self._time_to_seconds(end_time)
                
                segments.append(SubtitleSegment(
                    index=len(segments) + 1,
                    start_time=start_time,
                    end_time=end_time,
                    text=text,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds
                ))
                
            except Exception as e:
                logger.debug(f"Failed to parse VTT block: {e}")
        
        return segments
    
    def _parse_ass(self, ass_file: Path) -> List[SubtitleSegment]:
        """Parse ASS/SSA subtitle file."""
        segments = []
        
        with open(ass_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find [Events] section
        events_match = re.search(r'\[Events\](.*?)(?:\[|$)', content, re.DOTALL)
        if not events_match:
            return []
        
        events_content = events_match.group(1)
        
        # Parse Format line
        format_match = re.search(r'Format:\s*(.+)', events_content)
        if not format_match:
            return []
        
        format_fields = [f.strip() for f in format_match.group(1).split(',')]
        
        # Find index of relevant fields
        try:
            start_idx = format_fields.index('Start')
            end_idx = format_fields.index('End')
            text_idx = format_fields.index('Text')
        except ValueError:
            return []
        
        # Parse dialogue lines
        for line in events_content.split('\n'):
            line = line.strip()
            if not line.startswith('Dialogue:'):
                continue
            
            parts = line[len('Dialogue:'):].split(',', len(format_fields) - 1)
            if len(parts) < len(format_fields):
                continue
            
            try:
                start_time = parts[start_idx].strip()
                end_time = parts[end_idx].strip()
                text = ','.join(parts[text_idx:]).strip()
                
                # Remove ASS styling codes
                text = re.sub(r'\{[^}]*\}', '', text)
                
                start_seconds = self._time_to_seconds(start_time)
                end_seconds = self._time_to_seconds(end_time)
                
                segments.append(SubtitleSegment(
                    index=len(segments) + 1,
                    start_time=start_time,
                    end_time=end_time,
                    text=text,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds
                ))
                
            except Exception as e:
                logger.debug(f"Failed to parse ASS line: {e}")
        
        return segments
    
    def _time_to_seconds(self, time_str: str) -> float:
        """Convert time string to seconds.
        
        Supports formats:
        - HH:MM:SS,mmm or HH:MM:SS.mmm
        - MM:SS.mmm
        """
        time_str = time_str.replace(',', '.')
        
        parts = time_str.split(':')
        
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
        elif len(parts) == 2:
            hours = 0
            minutes = int(parts[0])
            seconds = float(parts[1])
        else:
            return 0.0
        
        return hours * 3600 + minutes * 60 + seconds


class WhisperTranscriber:
    """Audio transcription using Whisper."""
    
    def __init__(
        self,
        model: str = 'base',
        language: str = 'zh',
        device: str = 'cpu'
    ):
        """Initialize Whisper transcriber.
        
        Args:
            model: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
            language: Language code ('zh' for Chinese, 'en' for English)
            device: Device to use ('cpu', 'cuda')
        """
        self.model_name = model
        self.language = language
        self.device = device
        self._model = None
        self._available = False
        
        self._init_model()
    
    def _init_model(self):
        """Initialize Whisper model."""
        try:
            import whisper
            self._model = whisper.load_model(self.model_name, device=self.device)
            self._available = True
            logger.info(f"Whisper model '{self.model_name}' loaded")
        except ImportError:
            logger.warning("Whisper not available. Install with: pip install openai-whisper")
        except Exception as e:
            logger.warning(f"Failed to load Whisper model: {e}")
    
    @property
    def available(self) -> bool:
        """Check if Whisper is available."""
        return self._available
    
    def transcribe(
        self, 
        audio_path: str | Path,
        include_timestamps: bool = True
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Transcribe audio file.
        
        Args:
            audio_path: Path to audio/video file.
            include_timestamps: Include segment timestamps.
            
        Returns:
            Tuple of (full_text, segments_list)
        """
        if not self._available:
            raise RuntimeError("Whisper not available")
        
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Transcribe
        result = self._model.transcribe(
            str(audio_path),
            language=self.language,
            verbose=False
        )
        
        full_text = result['text'].strip()
        
        segments = []
        if include_timestamps:
            for segment in result.get('segments', []):
                segments.append({
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'text': segment.get('text', '').strip()
                })
        
        return full_text, segments


class SemanticSegmenter:
    """Segment transcript by semantic meaning."""
    
    def __init__(
        self,
        max_segment_length: int = 500,
        min_segment_length: int = 100
    ):
        """Initialize semantic segmenter.
        
        Args:
            max_segment_length: Maximum characters per segment
            min_segment_length: Minimum characters per segment
        """
        self.max_segment_length = max_segment_length
        self.min_segment_length = min_segment_length
        
        # Sentence ending patterns
        self.sentence_endings = re.compile(
            r'[。！？.!?\n]|[\.\.\.]|[\u3002]'  # Chinese and English endings
        )
        
        # Topic transition patterns (Chinese)
        self.transition_patterns = [
            r'首先', r'其次', r'然后', r'最后',
            r'第一', r'第二', r'第三',
            r'一方面', r'另一方面',
            r'总之', r'综上所述', r'总而言之',
            r'接下来', r'现在', r'下面',
        ]
    
    def segment(
        self, 
        text: str,
        subtitles: Optional[List[SubtitleSegment]] = None
    ) -> List[Dict[str, Any]]:
        """Segment transcript by semantic meaning.
        
        Args:
            text: Full transcript text.
            subtitles: Optional subtitle segments for timing info.
            
        Returns:
            List of segmented sections with metadata.
        """
        if not text.strip():
            return []
        
        # If we have subtitles, use them as base segments
        if subtitles:
            return self._segment_from_subtitles(subtitles)
        
        # Otherwise, segment by semantic analysis
        return self._segment_by_semantics(text)
    
    def _segment_from_subtitles(
        self, 
        subtitles: List[SubtitleSegment]
    ) -> List[Dict[str, Any]]:
        """Group subtitles into semantic segments."""
        segments = []
        current_segment = {
            'text': '',
            'start_time': None,
            'end_time': None,
            'start_seconds': 0,
            'end_seconds': 0,
            'subtitle_count': 0
        }
        
        for sub in subtitles:
            if not current_segment['start_time']:
                current_segment['start_time'] = sub.start_time
                current_segment['start_seconds'] = sub.start_seconds
            
            current_segment['text'] += sub.text + ' '
            current_segment['subtitle_count'] += 1
            current_segment['end_time'] = sub.end_time
            current_segment['end_seconds'] = sub.end_seconds
            
            # Check if segment is complete
            if self._should_split_segment(current_segment['text']):
                segments.append({
                    'text': current_segment['text'].strip(),
                    'start_time': current_segment['start_time'],
                    'end_time': current_segment['end_time'],
                    'start_seconds': current_segment['start_seconds'],
                    'end_seconds': current_segment['end_seconds'],
                    'subtitle_count': current_segment['subtitle_count']
                })
                current_segment = {
                    'text': '',
                    'start_time': None,
                    'end_time': None,
                    'start_seconds': 0,
                    'end_seconds': 0,
                    'subtitle_count': 0
                }
        
        # Add remaining segment
        if current_segment['text'].strip():
            segments.append({
                'text': current_segment['text'].strip(),
                'start_time': current_segment['start_time'] or subtitles[0].start_time,
                'end_time': current_segment['end_time'] or subtitles[-1].end_time,
                'start_seconds': current_segment['start_seconds'],
                'end_seconds': current_segment['end_seconds'],
                'subtitle_count': current_segment['subtitle_count']
            })
        
        return segments
    
    def _segment_by_semantics(self, text: str) -> List[Dict[str, Any]]:
        """Segment text by semantic analysis."""
        segments = []
        
        # Split into sentences
        sentences = self.sentence_endings.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        current_segment = []
        current_length = 0
        
        for sentence in sentences:
            current_segment.append(sentence)
            current_length += len(sentence)
            
            # Check if we should split
            if current_length >= self.min_segment_length:
                # Check for transition patterns
                if self._has_transition(sentence) or current_length >= self.max_segment_length:
                    segment_text = ' '.join(current_segment)
                    segments.append({
                        'text': segment_text,
                        'length': len(segment_text)
                    })
                    current_segment = []
                    current_length = 0
        
        # Add remaining
        if current_segment:
            segment_text = ' '.join(current_segment)
            segments.append({
                'text': segment_text,
                'length': len(segment_text)
            })
        
        return segments
    
    def _should_split_segment(self, text: str) -> bool:
        """Check if current segment should be split."""
        if len(text) < self.min_segment_length:
            return False
        
        if len(text) >= self.max_segment_length:
            return True
        
        # Check for transition patterns at end
        return self._has_transition(text.split()[-1] if text.split() else '')
    
    def _has_transition(self, text: str) -> bool:
        """Check if text contains transition pattern."""
        for pattern in self.transition_patterns:
            if pattern in text:
                return True
        return False


class VideoSubtitleLoader:
    """Load and process video files with subtitle extraction."""
    
    def __init__(
        self,
        extract_subtitles: bool = True,
        transcribe_audio: bool = True,
        whisper_model: str = 'base',
        language: str = 'zh',
        semantic_segmentation: bool = True,
    ):
        """Initialize video subtitle loader.
        
        Args:
            extract_subtitles: Extract embedded subtitles.
            transcribe_audio: Transcribe audio if no subtitles.
            whisper_model: Whisper model size.
            language: Language code.
            semantic_segmentation: Apply semantic segmentation.
        """
        self.extract_subtitles = extract_subtitles
        self.transcribe_audio = transcribe_audio
        self.whisper_model = whisper_model
        self.language = language
        self.semantic_segmentation = semantic_segmentation
        
        # Initialize components
        self._subtitle_extractor = SubtitleExtractor() if extract_subtitles else None
        self._transcriber = None
        self._segmenter = SemanticSegmenter() if semantic_segmentation else None
        
        if transcribe_audio:
            self._transcriber = WhisperTranscriber(
                model=whisper_model,
                language=language
            )
    
    def load(self, file_path: str | Path) -> Dict[str, Any]:
        """Load and process a video file.
        
        Args:
            file_path: Path to video/audio file.
            
        Returns:
            Dict with text content and metadata.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Compute document hash
        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"
        
        # Extract subtitles or transcribe
        subtitles = []
        full_text = ""
        segments = []
        
        # Try subtitle extraction first
        if self._subtitle_extractor and self._subtitle_extractor.ffmpeg_available:
            subtitles = self._subtitle_extractor.extract_subtitles(path, language=self.language)
            
            if subtitles:
                full_text = ' '.join(s.text for s in subtitles)
                logger.info(f"Extracted {len(subtitles)} subtitle segments")
        
        # Fallback to transcription
        if not full_text.strip() and self._transcriber and self._transcriber.available:
            full_text, transcribe_segments = self._transcriber.transcribe(path)
            segments = transcribe_segments
            logger.info(f"Transcribed audio: {len(full_text)} characters")
        
        # Apply semantic segmentation
        if self._segmenter:
            segments = self._segmenter.segment(full_text, subtitles if subtitles else None)
        
        # Build result
        result = {
            'id': doc_id,
            'doc_hash': doc_hash,
            'source_path': str(path),
            'doc_type': self._detect_doc_type(path),
            'full_text': full_text,
            'subtitles': [
                {
                    'index': s.index,
                    'start_time': s.start_time,
                    'end_time': s.end_time,
                    'text': s.text,
                    'start_seconds': s.start_seconds,
                    'end_seconds': s.end_seconds,
                }
                for s in subtitles
            ],
            'segments': segments,
            'metadata': {
                'subtitle_count': len(subtitles),
                'segment_count': len(segments),
                'total_duration': subtitles[-1].end_seconds if subtitles else 0,
                'extraction_method': 'subtitle' if subtitles else ('transcription' if full_text else 'none'),
            }
        }
        
        return result
    
    def _detect_doc_type(self, path: Path) -> str:
        """Detect document type from extension."""
        ext = path.suffix.lower()
        
        video_exts = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
        audio_exts = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
        
        if ext in video_exts:
            return 'video'
        elif ext in audio_exts:
            return 'audio'
        else:
            return 'media'
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()