"""
Module to handle and manage OSI trace files.
"""

import lzma
from pathlib import Path
import struct

from abc import ABC, abstractmethod

from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader

from osi3.osi_sensorview_pb2 import SensorView
from osi3.osi_sensorviewconfiguration_pb2 import SensorViewConfiguration
from osi3.osi_groundtruth_pb2 import GroundTruth
from osi3.osi_hostvehicledata_pb2 import HostVehicleData
from osi3.osi_sensordata_pb2 import SensorData
from osi3.osi_trafficcommand_pb2 import TrafficCommand
from osi3.osi_trafficcommandupdate_pb2 import TrafficCommandUpdate
from osi3.osi_trafficupdate_pb2 import TrafficUpdate
from osi3.osi_motionrequest_pb2 import MotionRequest
from osi3.osi_streamingupdate_pb2 import StreamingUpdate


MESSAGES_TYPE = {
    "SensorView": SensorView,
    "SensorViewConfiguration": SensorViewConfiguration,
    "GroundTruth": GroundTruth,
    "HostVehicleData": HostVehicleData,
    "SensorData": SensorData,
    "TrafficCommand": TrafficCommand,
    "TrafficCommandUpdate": TrafficCommandUpdate,
    "TrafficUpdate": TrafficUpdate,
    "MotionRequest": MotionRequest,
    "StreamingUpdate": StreamingUpdate,
}


class OSITrace:
    """This class can import and decode OSI single- and multi-channel trace files."""
    
    @staticmethod
    def map_message_type(type_name):
        """Map the type name to the protobuf message type."""
        return MESSAGES_TYPE[type_name]

    @staticmethod
    def message_types():
        """Message types that OSITrace supports."""
        return list(MESSAGES_TYPE.keys())
    
    def __init__(self, path=None, type_name="SensorView", cache_messages=False, topic=None):
        """
        Initializes the trace reader depending on the trace file format.
        
        Args:
            path (str): The path to the trace file.
            type_name (str): The type name of the messages in the trace; check supported message types with `OSITrace.message_types()`.
            cache_messages (bool): Whether to cache messages in memory (only applies to single-channel traces).
            topic (str): The topic name for multi-channel traces (only applies to multi-channel traces); Using the first available topic if not specified.
        """
        self.reader = None
        self.path = None

        if path is not None:
            self.reader = self._init_reader(Path(path), type_name, cache_messages, topic)
            
    def _init_reader(self, path, type_name, cache_messages, topic):
        if not path.exists():
            raise FileNotFoundError("File not found")

        if path.suffix.lower() == ".mcap":
            reader = OSITraceMulti(path, topic)
            if reader.get_message_type() != type_name:
                raise ValueError(f"Channel message type '{reader.get_message_type()}' does not match expected type '{type_name}'")
            return reader
        elif path.suffix.lower() in [".osi", ".lzma", ".xz"]:
            return OSITraceSingle(str(path), type_name, cache_messages)
        else:
            raise ValueError(f"Unsupported file format: '{path.suffix}'")

    def from_file(self, path, type_name="SensorView", cache_messages=False, topic=None):
        """
        Initializes the trace reader depending on the trace file format.
        
        Args:
            path (str): The path to the trace file.
            type_name (str): The type name of the messages in the trace; check supported message types with `OSITrace.message_types()`.
            cache_messages (bool): Whether to cache messages in memory (only applies to single-channel traces).
            topic (str): The topic name for multi-channel traces (only applies to multi-channel traces); Using the first available topic if not specified.
        """
        self.reader = self._init_reader(Path(path), type_name, cache_messages, topic)

    def restart(self, index=None):
        """
        Restart the trace reader.

        Note:
            Multi-channel traces don't support restarting from a specific index.
        """
        return self.reader.restart(index)

    def __iter__(self):
        return self.reader.__iter__()

    def close(self):
        return self.reader.close()

    def retrieve_offsets(self, limit=None):
        if isinstance(self.reader, OSITraceSingle):
            return self.reader.retrieve_offsets(limit)
        raise NotImplementedError("Offsets are only supported for single-channel traces.")

    def retrieve_message(self, index=None, skip=False):
        if isinstance(self.reader, OSITraceSingle):
            return self.reader.retrieve_message(index, skip)
        raise NotImplementedError("Index-based message retrieval is only supported for single-channel traces.")

    def get_message_by_index(self, index):
        if isinstance(self.reader, OSITraceSingle):
            return self.reader.get_message_by_index(index)
        raise NotImplementedError("Index-based message retrieval is only supported for single-channel traces.")

    def get_messages_in_index_range(self, begin, end):
        if isinstance(self.reader, OSITraceSingle):
            return self.reader.get_messages_in_index_range(begin, end)
        raise NotImplementedError("Index-based message retrieval is only supported for single-channel traces.")

    def get_available_topics(self):
        if isinstance(self.reader, OSITraceMulti):
            return self.reader.get_available_topics()
        raise NotImplementedError("Getting available topics is only supported for multi-channel traces.")
    
    def get_file_metadata(self):
        if isinstance(self.reader, OSITraceMulti):
            return self.reader.get_file_metadata()
        raise NotImplementedError("Getting file metadata is only supported for multi-channel traces.")
    
    def get_channel_metadata(self):
        if isinstance(self.reader, OSITraceMulti):
            return self.reader.get_channel_metadata()
        raise NotImplementedError("Getting channel metadata is only supported for multi-channel traces.")


class ReaderBase(ABC):
    """Common interface for trace readers"""
    @abstractmethod
    def restart(self, index=None):
        pass
    
    @abstractmethod
    def __iter__(self):
        pass

    @abstractmethod
    def close(self):
        pass


class OSITraceSingle(ReaderBase):
    """OSI single-channel trace reader"""
    
    def __init__(self, path=None, type_name="SensorView", cache_messages=False):
        self.type = OSITrace.map_message_type(type_name)
        self.file = None
        self.current_index = None
        self.message_offsets = None
        self.read_complete = False
        self.message_cache = {} if cache_messages else None
        self._header_length = 4
        if path:
            self.from_file(path, type_name, cache_messages)

    def from_file(self, path, type_name="SensorView", cache_messages=False):
        """Import a trace from a file"""
        self.type = OSITrace.map_message_type(type_name)

        if path.lower().endswith((".lzma", ".xz")):
            self.file = lzma.open(path, "rb")
        else:
            self.file = open(path, "rb")

        self.read_complete = False
        self.current_index = 0
        self.message_offsets = [0]
        self.message_cache = {} if cache_messages else None

    def retrieve_offsets(self, limit=None):
        """Retrieve the offsets of the messages from the file."""
        if not self.read_complete:
            self.current_index = len(self.message_offsets) - 1
            self.file.seek(self.message_offsets[-1], 0)
        while not self.read_complete and (
            not limit or len(self.message_offsets) <= limit
        ):
            self.retrieve_message(skip=True)
        return self.message_offsets

    def retrieve_message(self, index=None, skip=False):
        """Retrieve the next message from the file at the current position or given index, or skip it if skip is true."""
        if index is not None:
            self.current_index = index
            self.file.seek(self.message_offsets[index], 0)
        if self.message_cache is not None and self.current_index in self.message_cache:
            message = self.message_cache[self.current_index]
            self.current_index += 1
            if self.current_index == len(self.message_offsets):
                self.file.seek(0, 2)
            else:
                self.file.seek(self.message_offsets[self.current_index], 0)
            if skip:
                return self.message_offsets[self.current_index]
            else:
                return message
        start = self.file.tell()
        header = self.file.read(self._header_length)
        if len(header) < self._header_length:
            if start == self.message_offsets[-1]:
                self.message_offsets.pop()
                self.read_complete = True
            self.file.seek(start, 0)
            return None
        message_length = struct.unpack("<L", header)[0]
        if skip:
            new_pos = self.file.seek(message_length, 1)
            if new_pos - start < message_length + self._header_length:
                if start == self.message_offsets[-1]:
                    self.message_offsets.pop()
                    self.read_complete = True
                self.file.seek(start, 0)
                return None
            self.current_index += 1
            if start == self.message_offsets[-1]:
                self.message_offsets.append(new_pos)
            return new_pos
        message_data = self.file.read(message_length)
        if len(message_data) < message_length:
            if start == self.message_offsets[-1]:
                self.message_offsets.pop()
                self.read_complete = True
            self.file.seek(start, 0)
            return None
        self.current_index += 1
        message = self.type()
        message.ParseFromString(message_data)
        if start == self.message_offsets[-1]:
            if self.message_cache is not None:
                self.message_cache[len(self.message_offsets) - 1] = message
            self.message_offsets.append(self.file.tell())
        return message

    def restart(self, index=None):
        """Restart the reading of the file from the beginning or from a given index."""
        self.current_index = index if index else 0
        self.file.seek(self.message_offsets[self.current_index], 0)

    def __iter__(self):
        while message := self.retrieve_message():
            yield message

    def get_message_by_index(self, index):
        """
        Get a message by its index.
        """
        if index >= len(self.message_offsets):
            self.retrieve_offsets(index)
        if self.message_cache is not None and index in self.message_cache:
            return self.message_cache[index]
        return self.retrieve_message(index=index)

    def get_messages(self):
        """
        Yield an iterator over all messages in the file.
        """
        return self.get_messages_in_index_range(0, None)

    def get_messages_in_index_range(self, begin, end):
        """
        Yield an iterator over messages of indexes between begin and end included.
        """
        if begin >= len(self.message_offsets):
            self.retrieve_offsets(begin)
        self.restart(begin)
        current = begin
        while end is None or current < end:
            if self.message_cache is not None and current in self.message_cache:
                yield self.message_cache[current]
            else:
                message = self.retrieve_message()
                if message is None:
                    break
                yield message
            current += 1

    def close(self):
        if self.file:
            self.file.close()
        self.file = None
        self.current_index = None
        self.message_cache = None
        self.message_offsets = None
        self.read_complete = False
        self.read_limit = None
        self.type = None


class OSITraceMulti(ReaderBase):
    """OSI multi-channel trace reader"""

    def __init__(self, path, topic):
        self.path = Path(path)
        self._file = open(self.path, "rb")
        self.mcap_reader = make_reader(self._file, decoder_factories=[DecoderFactory()])
        self._summary = self.mcap_reader.get_summary()
        available_topics = self.get_available_topics()
        if topic == None:
            topic = available_topics[0]
        if topic not in available_topics:
            raise ValueError(f"The requested topic '{topic}' is not present in the trace file.")
        self.topic = topic
    
    def restart(self, index=None):
        if index != None:
            raise NotImplementedError("Restarting from a given index is not supported for multi-channel traces.")
        if hasattr(self, "_iter"):
            del self._iter

    def __iter__(self):
        """Stateful iterator over the channel's messages in log time order."""
        if not hasattr(self, "_iter"):
            self._iter = self.mcap_reader.iter_decoded_messages(topics=[self.topic])
        for message in self._iter:
            yield message.decoded_message
    
    def close(self):
        self._file.close()

    def get_available_topics(self):
        return [channel.topic for id, channel in self._summary.channels.items()]

    def get_file_metadata(self):
        metadata = []
        for metadata_entry in self.mcap_reader.iter_metadata():
            metadata.append(metadata_entry)
        return metadata

    def get_channel_metadata(self):
        for id, channel in self._summary.channels.items():
            if channel.topic == self.topic:
                return channel.metadata
        return None
    
    def get_message_type(self):
        for channel_id, channel in self._summary.channels.items():
            if channel.topic == self.topic:
                schema = self._summary.schemas[channel.schema_id]
                if schema.name.startswith("osi3."):
                    return schema.name[len("osi3.") :]
                else:
                    raise ValueError(f"Schema '{schema.name}' is not an 'osi3.' schema.")
        return None
