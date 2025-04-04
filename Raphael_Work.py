# -*- coding: utf-8 -*-
"""
@author: RDanjoux, Thermal Based Support Team
"""

# Import fnv modules
import fnv
import fnv.reduce
import fnv.file


# Other imports
import numpy as np
from matplotlib import pyplot as plt
from tkinter import filedialog
import tkinter
import os
import exifread
from skimage.exposure import equalize_hist


#%% Browse to file

root = tkinter.Tk()
root.withdraw()
root.call('wm', 'attributes', '.', '-topmost', True)

currdir = os.getcwd()
path = filedialog.askopenfilename(filetypes = (("Radiometric files", ["*.seq", "*.jpg", "*.ats", "*.sfmov", "*.img","*.fcf","*.ptw"]), ("All files", "*")))


#%% Set unit. Import data and TimeStamp from Metadata.

im = fnv.file.ImagerFile(path)              # open the file
print(path)

# Set desired units
# Possible units are COUNTS, TEMPERATURE_FACTORY, TEMPERATURE_USER,  RADIANCE_FACTORY and RADIANCE_USER

if im.has_unit(fnv.Unit.TEMPERATURE_FACTORY):
    # Set unit to temperature, if available
    im.unit = fnv.Unit.TEMPERATURE_FACTORY
    im.temp_type = fnv.TempType.CELSIUS

else:
    # If file has no temperature calibration, use counts instead
    im.unit = fnv.Unit.COUNTS

#%% Object Parameters.
# What follows is just an example!
# It shows how to modify the emissivity.
# The same procecedure can be applied to any other Object Parameters. Find their names in the workspace.
# Setting new Object Parameters shall be done prior to calling for frames in final definition.
ObjParam=im.object_parameters
ObjParam.emissivity = 0.9
im.object_parameters = ObjParam

#%% Import data and TimeStamp from Metadata.
# What follows is just an example!
# Image data stored in a numpy 3D array (like a voxel) and TimeStamp stored in a numpy 1D array.
# TimeStamp equal to the number of seconds and microseconds elapsed since January 1 of the current year.
myArray=np.zeros((im.num_frames, im.height, im.width))
TimeStamp=np.zeros((im.num_frames))
for i in range(im.num_frames):
    im.get_frame(i)
    myArray[i]=np.array(im.final, copy=False).reshape((im.height, im.width))

max_value = np.max(myArray)
min_value = np.min(myArray)

#%% Display the loaded file for a short time. Can be a single frame or a movie;

#Display time depending on number of frames. Values are arbitrary.
if im.num_frames == 1:
    Tempo = 5
if im.num_frames >= 2:
    Tempo = 0.2
if im.num_frames >=10:
    Tempo = 0.05
if im.num_frames >=100:
    Tempo = 0.0001
"""
#Switch to full screen
figManager = plt.get_current_fig_manager()
figManager.full_screen_toggle()
"""
# Display frame then clear it to the next one. This will improve display speed significantly.
for i in range(im.num_frames):
    plt.suptitle('Display IR Image Camera File SDK')
    # Display in Fixed scale
    # plt.imshow(myArray[i],cmap="gray",aspect="equal",vmax=max_value,vmin=min_value)
    plt.imshow(myArray[i],cmap="gray",aspect="equal")
    plt.colorbar(format='%.2f')
    display_text="Frame "+str(i+1)+"/"+str(im.num_frames)
    plt.text(0,-10,display_text)
    plt.pause(Tempo)
    plt.clf()

'''
    # Display with histogram equalization. Scikit-image is needed here.
    plt.imshow(equalize_hist(myArray[i]),cmap="hsv")
    plt.colorbar(format='%.2f')
    display_text="Frame "+str(i+1)+"/"+str(im.num_frames)
    plt.text(0,-10,display_text)
    plt.pause(Tempo)
    plt.clf()
'''


# Close plot
plt.close()

#%% Dispose image
im = None                                   # done with the file
