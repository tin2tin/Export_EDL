"""
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# io_export_sequencer_edl.py -- Export of CMX 3600 Edit Decision List ("EDL") files.
# by Tintwotin

# Additional functions by Campbell Barton, William R. Zwicky, szaszak and
# 'operator_file_export.py'.

# HOW TO: Collect all video in one track and all audio in as few tracks as possible.
# NB: Only Movie, cross dissolves and audio are supported in exports.
# NB: Drop frame not supported.

# Missing: add try and execept to list for out of bounce errors. Maybe not needed since transitions can only exist in time line with a previous and a nex clip.
# Missing: Detect dropframe rates - and stop export
# Missing: register/unregister?
# Missing: Clean up
# Missing option: to save each track as an individual file.

import bpy
import os
import sys

bl_info = {
    "name": "Export EDL",
    "author": "Tintwotin",
    "version": (0, 5),
    "blender": (2, 78, 0),
    "location": "File > Export > Timeline (.edl)",
    "description": "Save a CMX formatted EDL from the Timeline",
    "warning": "",
    "wiki_url": ""
                "",
    "category": "Import-Export",
}

# checkFPS function by szaszak
def checkFPS(): 
    '''Checks project's FPS compatibility with EDL's FPSs'''
    validFPS = [24, 25, 30, 60] # EDL FPSs
    #validFPS = [23.976, 24, 24.975, 25, 29.97, 30, 59.94, 60] # EDL FPSs    
    render = bpy.context.scene.render
    fps = round((render.fps / render.fps_base), 3)

    if fps in validFPS:
        if fps.is_integer():
            fps = int(fps)
            timecode = "timecode_%s" % fps
        else:
            timecode = "timecode_%s" % str(fps).replace(".", "")
    else:
        raise RuntimeError(
            "Framerate \'" + str(fps) + "\' not supported by EDL. "
            "Change to 24, 25, 30, 60."
            #"Change to 23.976, 24, 24.975, 25, 29.97, 30, 59.94, 60."            
        )
    return fps, timecode

checkFPS()

# TimeCode class by Campbell Barton
class TimeCode:
    """
    Simple timecode class
    also supports conversion from other time strings used by EDL
    """
    __slots__ = (
        "fps",
        "hours",
        "minutes",
        "seconds",
        "frame",
    )

    def __init__(self, data, fps):
        self.fps = fps
        if type(data) == str:
            self.from_string(data)
            frame = self.as_frame()
            self.from_frame(frame)
        else:
            self.from_frame(data)

    def from_string(self, text):
        # hh:mm:ss:ff
        # No dropframe support yet

        if text.lower().endswith("mps"):  # 5.2mps
            return self.from_frame(int(float(text[:-3]) * self.fps))
        elif text.lower().endswith("s"):  # 5.2s
            return self.from_frame(int(float(text[:-1]) * self.fps))
        elif text.isdigit():  # 1234
            return self.from_frame(int(text))
        elif ":" in text:  # hh:mm:ss:ff
            text = text.replace(";", ":").replace(",", ":").replace(".", ":")
            text = text.split(":")

            self.hours = int(text[0])
            self.minutes = int(text[1])
            self.seconds = int(text[2])
            self.frame = int(text[3])
            return self
        else:
            print("ERROR: could not convert this into timecode %r" % text)
            return self

    def from_frame(self, frame):

        if frame < 0:
            frame = -frame
            neg = True
        else:
            neg = False

        fpm = 60 * self.fps
        fph = 60 * fpm

        if frame < fph:
            self.hours = 0
        else:
            self.hours = int(frame / fph)
            frame = frame % fph

        if frame < fpm:
            self.minutes = 0
        else:
            self.minutes = int(frame / fpm)
            frame = frame % fpm

        if frame < self.fps:
            self.seconds = 0
        else:
            self.seconds = int(frame / self.fps)
            frame = frame % self.fps

        self.frame = frame

        if neg:
            self.frame = -self.frame
            self.seconds = -self.seconds
            self.minutes = -self.minutes
            self.hours = -self.hours

        return self

    def as_frame(self):
        abs_frame = self.frame
        abs_frame += self.seconds * self.fps
        abs_frame += self.minutes * 60 * self.fps
        abs_frame += self.hours * 60 * 60 * self.fps

        return abs_frame

    def as_string(self):
        self.from_frame(int(self))
        return "%.2d:%.2d:%.2d:%.2d" % (self.hours, self.minutes, self.seconds, self.frame)

    def __repr__(self):
        return self.as_string()

    # Numeric stuff, may as well have this
    def __neg__(self):
        return TimeCode(-int(self), self.fps)

    def __int__(self):
        return self.as_frame()

    def __sub__(self, other):
        return TimeCode(int(self) - int(other), self.fps)

    def __add__(self, other):
        return TimeCode(int(self) + int(other), self.fps)

    def __mul__(self, other):
        return TimeCode(int(self) * int(other), self.fps)

    def __div__(self, other):
        return TimeCode(int(self) // int(other), self.fps)

    def __abs__(self):
        return TimeCode(abs(int(self)), self.fps)

    def __iadd__(self, other):
        return self.from_frame(int(self) + int(other))

    def __imul__(self, other):
        return self.from_frame(int(self) * int(other))

    def __idiv__(self, other):
        return self.from_frame(int(self) // int(other))
# end timecode

#EDLBlock by William R. Zwicky 
class EDLBlock:
    def __init__(self):
        self.id = 0
        """Num, 3 digits, officially 001-999. Non-num makes row a comment."""
        self.reel = None
        """Reference to media file or tape.
           Officially: 4-digit num, optional B; or BL for black,
           or AX for aux source.
           Unofficially: any string."""
        self.channels = None
        """A=audio1,V=video1,B=A+V,A2=audio2,A2/V=A2+V,AA=A1+A2,AA/V=A1+A2+V"""
        self.transition = None
        """C=cut,
           D=dissolve,
           Wxxx=wipe type xxx,
           KB=key background,
           K=key foreground,
           KO=key foreground mask"""
        self.transDur = None
        """3-digit duration, in frames, or lone F"""
        self.srcIn = None
        """timecode (hh:mm:ss:ff)"""
        self.srcOut = None
        """timecode (hh:mm:ss:ff)"""
        self.recIn = None
        """timecode (hh:mm:ss:ff)"""
        self.recOut = None
        """timecode (hh:mm:ss:ff). Either out-time or duration.
           Ignored on read; clip length is srcOut-srcIn."""
        self.file = None
        """filename and extention, but no path"""  
                
#EDL Class by 2015 William R. Zwicky
class EDL(list):
    def __init__(self):
        self.title = None
        self.dropframe = False
        self.reels = {}
        #self.edits = []

    def load(filename):
        pass

    def savePremiere(self):
        # CMX 3600:
        #   111^^222^^3333^^4444^555^666666666666^777777777777^888888888888^999999999999^
        # Old Lightworks converter:
        #   003  E00706EU  V     D    030 00:00:26:29 00:00:32:10 00:00:01:02 00:00:07:13
        #   111^^22222222^3333^4444^555^^66666666666^77777777777^88888888888^99999999999
        # Export from Premiere:
        #   003  AX       AA    C        00:00:00:10 00:02:03:24 00:00:53:25 00:02:57:09
        #   * FROM CLIP NAME: Ep6_Sc2 - Elliot tries again with Tiff.mp4
        # Export from Davinci Resolve
        #   002  10_sec   V     D    012 00:00:02:20 00:00:04:19 01:00:02:20 01:00:04:19
        #   111^^22222222^3333^^4444^555^66666666666^77777777777^88888888888^99999999999        
        context = bpy.context
        scene = context.scene
        s=""
        render = bpy.context.scene.render
        fps = int(round((render.fps / render.fps_base), 3))        
        
        if not not self.title:
            s="TITLE: " + self.title+"  "+str(fps)+" fps\n"
        if self.dropframe:
            s += "FCM: DROP FRAME"+"\n"
        else:
            s += "FCM: NON DROP FRAME"+"\n\n"
            
        #s += "FRAMERATE: "+str(scene.render.fps)+"\n\n" #not supported

        for block in self:
            s += "%03d  %-8s %-4s  %-4s %03s %-11s %-11s %-11s %-11s" \
                % (block.id, block.reel, block.channels,
                   block.transition, block.transDur,
                   block.srcIn, block.srcOut, block.recIn, block.recOut)+ "\n"
            if block.file !="":
                s += "* FROM CLIP NAME: " + block.file + "\n\n"
        print(s)
        return(s)
    

    
def write_edl(context, filepath, use_some_setting):
    print("Running export edl...\n")
    
    context = bpy.context
    scene = context.scene
    vse = scene.sequence_editor
    render = bpy.context.scene.render
    edl_fps = int(round((render.fps / render.fps_base), 3)) 
    id_count=1

    e = EDL()
    e.title = os.path.splitext(bpy.path.basename(bpy.context.blend_data.filepath))[0] 
    e.dropframe=False

    def start(strip):
        return strip.frame_final_start 

    def end(strip):
        return strip.frame_final_start + strip.frame_final_duration

    def channel(strip):
        return strip.channel

    # Sort the clips in left to right order & in channels order
    seq_strips = bpy.context.scene.sequence_editor.sequences
    strips_by_start = sorted(seq_strips, key=start)
    strips_by_start_and_channel = sorted(strips_by_start, key=channel, reverse=True)
    
    jump=0
    cnt=0
    
    max_channel=strips_by_start_and_channel[0].channel
    current_channel=0

    # Add values to EDL string
    
    # Loop for video
    for strip in strips_by_start_and_channel:
        b = EDLBlock()
        b.id = id_count

        if strip.type in ['MOVIE'] and jump==0:
            try:
                reelname = bpy.path.basename(strip.filepath)
                b.file=reelname
                reelname = os.path.splitext(reelname)[0]        
                b.reel = ((reelname+"        ")[0:8])                
                b.channels = "V"#+str(max_channel-strip.channel+1)
                b.transition = "C   "
                b.transDur = "   "
                b.srcIn = TimeCode(strip.frame_offset_start,edl_fps)
                b.srcOut = TimeCode(strip.frame_offset_start+strip.frame_final_duration,edl_fps)
                b.recIn = TimeCode(strip.frame_final_start,edl_fps)
                b.recOut = TimeCode(strip.frame_final_end,edl_fps)                
                e.append(b)  
                id_count=id_count+1  
            except:
                id_count=id_count    
        elif strip.type in ['MOVIE'] and jump==1:  
            # jump=1 means that current strip has been used in previous transition
            jump=0       
        elif strip.type in ['CROSS']:
            try:
                # 1. Clip in the transition        
                reelname = bpy.path.basename(strip.input_1.filepath)
                b.file=""#reelname
                reelname = os.path.splitext(reelname)[0]        
                b.reel = ((reelname+"        ")[0:8])        
                b.channels = "V"#+str(max_channel-strip.channel+1)         
                b.transition = "C   "[0:4]
                b.transDur = "   "                                       
                b.srcIn = TimeCode(strips_by_start_and_channel[cnt-1].frame_offset_start+strips_by_start_and_channel[cnt-1].frame_final_duration,edl_fps)
                b.srcOut = TimeCode(strips_by_start_and_channel[cnt-1].frame_offset_start+strips_by_start_and_channel[cnt-1].frame_final_duration,edl_fps)#TimeCode(strip.frame_start+strip.frame_final_duration,edl_fps)
                b.recIn = TimeCode(strip.input_1.frame_final_end,edl_fps)
                b.recOut = TimeCode(strip.input_1.frame_final_end,edl_fps)#TimeCode(strip.frame_final_end,edl_fps)                
                e.append(b)        
                # 2. Clip in the transition
                b = EDLBlock()
                b.id = id_count
                reelname = bpy.path.basename(strip.input_2.filepath)
                b.file= bpy.path.basename(strip.input_1.filepath) + "\n* TO CLIP NAME: "+reelname
                reelname = os.path.splitext(reelname)[0]        
                b.reel = ((reelname+"        ")[0:8])        
                b.channels = "V"#+str(max_channel-strip.channel+1)        
                b.transition = "D   "[0:4]  
                b.transDur = (str(strip.frame_final_duration)).zfill(3)
                b.srcIn = TimeCode(strips_by_start_and_channel[cnt+1].frame_offset_start-strip.frame_final_duration, edl_fps)
                b.srcOut = TimeCode(strips_by_start_and_channel[cnt+1].frame_offset_start+strips_by_start_and_channel[cnt+1].frame_final_duration, edl_fps)
                b.recIn = TimeCode(strip.frame_final_start,edl_fps)
                b.recOut = TimeCode(strips_by_start_and_channel[cnt+1].frame_final_end,edl_fps)                
                e.append(b)
                id_count=id_count+1  
                jump=1
            except:
                jump=0                                                   

        try:
            next_channel=max_channel-strips_by_start_and_channel[cnt+1].channel
        except: 
            next_channel=max_channel+1
        #print(str(cnt)+" "+str(b.transition))
        #print(str(next_channel)+"   "+str(current_channel))
        
        if next_channel!=current_channel and b.srcIn !=None:
            e.title = os.path.splitext(bpy.path.basename(filepath))[0]+"_V_"+str(max_channel-strip.channel+1).zfill(2)
            edl_filepath=str(filepath[:-4])+"_V_"+str(max_channel-strip.channel+1).zfill(2)+".edl"
            f = open(edl_filepath, 'w', encoding='utf-8')
            f.write(e.savePremiere())
            f.close() 
            b=""
            b = EDLBlock()
            b.id = 1
            id_count=1
            current_channel=next_channel
            e = EDL()
            
        cnt+=1   
        
    # Loop for audio                           
    current_channel=0
    cnt=0 
    b=""
    b = EDLBlock()
    b.id = 1
    id_count=1 
    e = EDL()   
             
    for strip in strips_by_start_and_channel:    

        b = EDLBlock()
        b.id = id_count
        #id_count=id_count+1   
        if strip.type in ['SOUND']:
            reelname = bpy.path.basename(strip.sound.filepath)
            b.file=reelname
            reelname = os.path.splitext(reelname)[0]        
            b.reel = ((reelname+"        ")[0:8])        
            b.channels = "A"#+str(max_channel-strip.channel+1)
            b.transition = "C   "
            b.transDur = "   "
            b.srcIn = TimeCode(strip.frame_offset_start,edl_fps)
            b.srcOut = TimeCode(strip.frame_offset_start+strip.frame_final_duration,edl_fps)
            b.recIn = TimeCode(strip.frame_final_start,edl_fps)
            b.recOut = TimeCode(strip.frame_final_end,edl_fps)                
            e.append(b)                                      
            id_count=id_count+1

        try:
            next_channel=max_channel-strips_by_start_and_channel[cnt+1].channel+1
        except: 
            next_channel=max_channel+1
        #print(str(cnt)+str(b.srcIn))                
        #print(str(next_channel)+"  "+str(current_channel))    
        #print(b.srcIn)
        if next_channel!=current_channel and b.srcIn !=None:
            e.title = os.path.splitext(bpy.path.basename(filepath))[0]+"_A_"+str(max_channel-strip.channel+1).zfill(2)
            edl_filepath=str(filepath[:-4])+"_A_"+str(max_channel-strip.channel+1).zfill(2)+".edl"
            f = open(edl_filepath, 'w', encoding='utf-8')
            f.write(e.savePremiere())
            f.close() 
            b=""
            b = EDLBlock()
            b.id = 1
            id_count=1
            current_channel=next_channel
            e = EDL()
        cnt+=1
    return {'FINISHED'}


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class ExportEDL(Operator, ExportHelper):
    """Export Timeline as a Edit Decision List in CMX 3600 Format"""
    bl_idname = "export_timeline.edl"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export EDL"

    # ExportHelper mixin class uses this
    filename_ext = ".edl"

    filter_glob = StringProperty(
            default="*.edl",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_setting = BoolProperty(
            name="EDL Boolean",
            description="EDL Tooltip",
            default=True,
            )
                
    def execute(self, context):
        return write_edl(context, self.filepath, self.use_setting)

# Dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportEDL.bl_idname, text="Timeline (.edl)")


def register():
    bpy.utils.register_class(ExportEDL)
    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportEDL)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export_timeline.edl('INVOKE_DEFAULT')
    

