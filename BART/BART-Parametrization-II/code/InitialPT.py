# ****************************** START LICENSE *******************************
# Bayesian Atmospheric Radiative Transfer (BART), a code to infer
# properties of planetary atmospheres based on observed spectroscopic
# information.
# 
# This project was completed with the support of the NASA Planetary
# Atmospheres Program, grant NNX12AI69G, held by Principal Investigator
# Joseph Harrington. Principal developers included graduate students
# Patricio E. Cubillos and Jasmina Blecic, programmer Madison Stemm, and
# undergraduates M. Oliver Bowman and Andrew S. D. Foster.  The included
# 'transit' radiative transfer code is based on an earlier program of
# the same name written by Patricio Rojo (Univ. de Chile, Santiago) when
# he was a graduate student at Cornell University under Joseph
# Harrington.  Statistical advice came from Thomas J. Loredo and Nate
# B. Lust.
# 
# Copyright (C) 2015 University of Central Florida.  All rights reserved.
# 
# This is a test version only, and may not be redistributed to any third
# party.  Please refer such requests to us.  This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.
# 
# Our intent is to release this software under an open-source,
# reproducible-research license, once the code is mature and the first
# research paper describing the code has been accepted for publication
# in a peer-reviewed journal.  We are committed to development in the
# open, and have posted this code on github.com so that others can test
# it and give us feedback.  However, until its first publication and
# first stable release, we do not permit others to redistribute the code
# in either original or modified form, nor to publish work based in
# whole or in part on the output of this code.  By downloading, running,
# or modifying this code, you agree to these conditions.  We do
# encourage sharing any modifications with us and discussing them
# openly.
# 
# We welcome your feedback, but do not guarantee support.  Please send
# feedback or inquiries to:
# 
# Joseph Harrington <jh@physics.ucf.edu>
# Patricio Cubillos <pcubillos@fulbrightmail.org>
# Jasmina Blecic <jasmina@physics.ucf.edu>
# 
# or alternatively,
# 
# Joseph Harrington, Patricio Cubillos, and Jasmina Blecic
# UCF PSB 441
# 4111 Libra Drive
# Orlando, FL 32816-2385
# USA
# 
# Thank you for testing BART!
# ******************************* END LICENSE *******************************

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import scipy.constants   as sc

import PT        as pt
import reader    as rd
import constants as c

def initialPT(date_dir, tepfile, press_file, a1, a2, p1, p2, p3, T3_fac):
  """
  This function generates a non-inverted temperature profile using the
  parametrized model described in Madhusudhan & Seager (2009). It plots
  the profile to screen and save the figures in the output directory.  
  The generated PT profile is a semi-adiabatic profile with a bottom-layer
  temperature corresponding (within certain range) to the planetary
  effective temperature.

  Parameters
  ----------
  date_dir: String
     Directory where to save the output plots.
  tepfile: String
     Name of ASCII tep file with planetary system data.
  press_file: String
     Name of ASCII file with pressure array data.
  a1: Float
     Model exponential factor in Layer 1.
  a2: Float
     Model exponential factor in Layer 2.
  p1: Float
     Pressure boundary between Layers 1 and 2 (in bars).
  p3: Float
     Pressure boundary between Layers 2 and 3 (in bars).
  T3_fac: Float
     Multiplicative factor to set T3 (T3 = Teff * T3_fac).
     Empirically determined to be between (1, 1.5) to account
     for the possible spectral features.

  Notes
  -----
  See model details in Madhusudhan & Seager (2009):
  http://adsabs.harvard.edu/abs/2009ApJ...707...24M

  Returns
  -------
  T_smooth: 1D float ndarray
      Array of temperatures.

  Developers
  ----------
  Jasmina Blecic     jasmina@physics.ucf.edu
  Patricio Cubillos  pcubillos@fulbrightmail.org

  Revisions
  ---------
  2014-04-08  Jasmina   Written by
  2014-07-23  Jasmina   Added date_dir and PT profile arguments.
  2014-08-15  Patricio  Replaced call to PT_Initial by PT_NoInversion.
  2014-09-24  Jasmina   Updated documentation.
  """

  # Calculate the planetary effective temperature from the TEP file
  Teff = pt.planet_Teff(tepfile)

  # Calculate T3 temperature based on Teff
  T3 = float(T3_fac) * Teff

  # Read pressures from file
  p = pt.read_press_file(press_file)

  # Generate initial PT profile non inversion case Jasmina commented
  #PT, T_smooth = pt.PT_NoInversion(p, a1, a2, p1, p3, T3)

  # Generate initial PT profile inversion case Jasmina added
  PT, T_smooth = pt.PT_Inversion(p, params)

  # Take temperatures from PT generator
  T, T0, T1, T3 = PT[5], PT[7], PT[8], PT[9]

  # Plot raw PT profile
  plt.figure(1)
  plt.clf()
  plt.semilogy(PT[0], PT[1], '.', color = 'r'     )
  plt.semilogy(PT[2], PT[3], '.', color = 'b'     )
  plt.semilogy(PT[4], PT[5], '.', color = 'orange')
  # Jasmina added inversion case plotting
  plt.semilogy(PT[6], PT[7], '.', color = 'g'     )
  plt.title('Initial PT', fontsize=14)
  plt.xlabel('T [K]', fontsize=14)
  plt.ylabel('logP [bar]', fontsize=14)
  plt.xlim(0.9*T0, 1.1*T3)
  plt.ylim(max(p), min(p))

  # Save plot to current directory
  plt.savefig(date_dir + '/InitialPT.png') 

  # Plot Smoothed PT profile
  plt.figure(2)
  plt.clf()
  plt.semilogy(T_smooth, p, '-', color = 'b', linewidth=1)
  plt.title('Initial PT Smoothed', fontsize=14)
  plt.xlabel('T [K]'     , fontsize=14)
  plt.ylabel('logP [bar]', fontsize=14)
  plt.ylim(max(p), min(p))
  plt.xlim(0.9*T0, 1.1*T3)

  # Save plot to output directory
  plt.savefig(date_dir + '/InitialPTSmoothed.png') 

  return T_smooth

def initialPT2(date_dir, params, pressfile, mode, tepfile, tint=100.0):
  """
  Compute a Temperature profile.

  Parameters:
  -----------
  params: 1D Float ndarray
    Array of fitting parameters.
  pressfile: String
    File name of the pressure array.
  mode: String
    Chose the PT model: 'madhu' or 'line'.
  tepfile: String
    Filename of the planet's TEP file.
  tint: Float
    Internal planetary temperature.
  """
  # Read pressures from file -- small to large:
  pressure = pt.read_press_file(pressfile)

  # PT arguments:
  PTargs = [mode]

  # Read the TEP file:
  tep = rd.File(tepfile)
  # Stellar radius (in meters):
  rstar = float(tep.getvalue('Rs')[0]) * c.Rsun
  # Stellar temperature in K:
  tstar = float(tep.getvalue('Ts')[0])
  # Semi-major axis (in meters):
  sma   = float(tep.getvalue( 'a')[0]) * sc.au
  # Planetary radius (in meters):
  rplanet = float(tep.getvalue('Rp')[0]) * c.Rjup
  # Planetary mass (in kg):
  mplanet = float(tep.getvalue('Mp')[0]) * c.Mjup

  if mode == "line":
    # Planetary surface gravity (in cm s-2):
    gplanet = 100.0 * sc.G * mplanet / rplanet**2
    # Additional PT arguments:
    PTargs += [rstar, tstar, tint, sma, gplanet]

  # Jasmina added
  if mode == "madhu":
    # Additional PT arguments:
    PTargs += []

  # Calculate temperature, corresponds to pressure -- small to large
  Temp =  pt.PT_generator(pressure, params, PTargs)

  # Plot PT profile
  plt.figure(1)
  plt.semilogy(Temp, pressure, '-', color = 'r')
  plt.xlim(0.9*min(Temp), 1.1*max(Temp))
  plt.ylim(max(pressure), min(pressure))
  plt.title('Initial PT Line', fontsize=14)
  plt.xlabel('T [K]'     , fontsize=14)
  plt.ylabel('logP [bar]', fontsize=14)

  # Save plot to current directory
  plt.savefig(date_dir + 'InitialPT.png') 

  return Temp
