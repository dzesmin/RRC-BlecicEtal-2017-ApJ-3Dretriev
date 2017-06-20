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

"""
    This code runs and processes best-fit Transit run outputs.
    
    Functions
    ---------
    read_MCMC_out:
          Read the MCMC output log file. Extract the best fitting parameters.
    get_params:
	      Get correct number of all parameters from stepsize
    get_starData:
          Extract stellar temperature, radius, and mass from TEP file
    write_atmfile:
          Write best-fit atm file with scaled H2 and He to abundances sum of 1
    bestFit_tconfig:
          Write best-fit config file for best-fit Transit run
    callTransit:
          Call Transit to produce best-fit outputs. Plot MCMC posterior PT plot.
    plot_bestFit_Spectrum:
          Plot BART best-model spectrum

    Revisions
    ---------
    2015-05-03  Jasmina  Original implementation
    2015-07-12  Jasmina  Added documentation.
"""

import numpy as np
import reader as rd
import scipy.constants as sc
import scipy.special   as sp
import scipy.interpolate as si
from scipy.ndimage.filters import gaussian_filter1d as gaussf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import makeatm as mat
import PT as pt
import wine as w
import readtransit as rt
import constants as c

def read_MCMC_out(MCfile):
    """
    Read the MCMC output log file. Extract the best fitting parameters.
    """
    # Open file to read
    f = open(MCfile, 'r')
    lines = np.asarray(f.readlines())
    f.close() 

    # Find where the data starts and ends:
    for ini in np.arange(len(lines)):
        if lines[ini].startswith(' Best-fit params'):
            break
    ini += 1
    end = ini
    for end in np.arange(ini, len(lines)):
        if lines[end].strip() == "":
            break

    # Read data:
    data = np.zeros((end-ini, 4))
    for i in np.arange(ini, end):
        data[i-ini] = lines[i].split()
    bestP = data[:, 0]
    uncer = data[:, 1]
    SN    = data[:, 2] 
    mean  = data[:, 3] 

    return bestP, uncer, SN, mean


def get_params(bestP, stepsize, params):
    """
    Get correct number of all parameters from stepsize
    """
    j = 0
    allParams = np.zeros(len(stepsize))
    for i in np.arange(len(stepsize)):
        if stepsize[i] != 0.0:
            allParams[i] = bestP[j]
            j +=1
        else:
            allParams[i] = params[i]
            
    return allParams


def get_starData(tepfile):
    """
    Extract the Stellar temperature, radius, and mass from a TEP file.
    """
    # Open tepfile to read and get data:
    tep = rd.File(tepfile)

    # Get star mass in Mjup:
    Tstar = np.float(tep.getvalue('Ts')[0])

    # Get star radius in MKS units:
    Rstar = np.float(tep.getvalue('Rs')[0]) * c.Rsun

    # Get semi major axis in meters:
    sma = np.float(tep.getvalue('a')[0]) * sc.au

    # Get star loggstar:
    gstar = np.float(tep.getvalue('loggstar')[0])

    return Rstar, Tstar, sma, gstar


def write_atmfile(atmfile, molfit, rad, T_line, allParams, date_dir):
    """
    Write best-fit atm file with scaled H2 and He to abundances sum of 1.

    Parameters:
    -----------
    atmfile: String
      Atmospheric file to take the pressure and abundance profiles.
    molfit: 1D string ndarray
      List of molecule names to modify their abundances.
    rad: 1D float ndarray
      Modified radius of the atmospheric layers.
    T_line: 1D float ndarray
      Modified temperature of the atmospheric layers.
    allParams: 1D float ndarray
      List of scaling factors to modify the abundances of molfit molecules.
    date_dir: String
      Directory where to store the best-fit atmospheric file.
    """
    # Open atmfile to read
    f = open(atmfile, 'r')
    lines = np.asarray(f.readlines())
    f.close()

    # Get the molecules
    imol = np.where(lines == "#SPECIES\n")[0][0] + 1
    molecules = lines[imol].split()

    # Find the line where the layers info begins
    start = np.where(lines == "#TEADATA\n")[0][0] + 2 
    headers = lines[start-1].split()
    datalines = lines[start:]

    # Number of columns
    ncol = len(lines[start].split())

    # Number of layers
    ndata = len(datalines)  

    # Allocate space for pressure:
    pressure = np.zeros(ndata, np.double) 

    # Number of abundances (elements per line except Radius, Press and T) 
    nabun = len(lines[start].split()) - 3  

    data = np.zeros((ndata, len(headers)))
    for i in np.arange(ndata):
        data[i] = datalines[i].split()

    # Extract pressure data -- large to small:
    pressure = data[:,1]

    # Fill out the abundances array:
    abundances = np.zeros((len(molecules), ndata))
    for i in np.arange(len(molecules)):
        for j in np.arange(ndata):
            abundances[i] = data[:, i+3]

    # recognize which columns to take from the atmospheric file
    headers = lines[start-1].split()
    columns = np.zeros(len(molfit))
    for i in np.arange(len(molfit)):
        for j in np.arange(len(headers)):
            if molfit[i] == headers[j]:
                columns[i] = j

    # number of molecules to fit:
    nfit = len(molfit)
    abun_fact = allParams

    # multiply the abundances of molfit molecules
    for i in np.arange(len(columns)):
       abundances[columns[i]-3] = abundances[columns[i]-3] * 10**abun_fact[i]

    # ===== Scale H2 and He if sum abundances > 1 ===== #
    # Find index for Hydrogen and Helium
    molecules = np.asarray(molecules)
    iH2     = np.where(molecules=="H2")[0][0]
    iHe     = np.where(molecules=="He")[0][0]

    # Get H2/He abundance ratio:
    ratio = (abundances[iH2,:] / abundances[iHe,:])

    # Find which level has sum(abundances)>1 and get the difference
    q = np.sum(abundances, axis=0) - 1

    # Correct H2, and He abundances conserving their ratio:
    for i in np.arange(ndata):
    #    if q[i]>0:
            abundances[iH2, i] -= ratio[i] * q[i] / (1.0 + ratio[i])
            abundances[iHe, i] -=            q[i] / (1.0 + ratio[i])

    # open best fit atmospheric file
    fout = open(date_dir + 'bestFit.atm', 'w')
    fout.writelines(lines[:start])

    # Write atm file for each run
    for i in np.arange(ndata): 
        # Radius, pressure, and temp for the current line
        radi = str('%10.3f'%rad[i])
        presi = str('%10.4e'%pressure[i])
        tempi = str('%7.2f'%T_line[i])

        # Insert radii array
        fout.write(radi.ljust(10) + ' ')

        # Insert results from the current line (T-P) to atm file
        fout.write(presi.ljust(10) + ' ')
        fout.write(tempi.ljust(7) + ' ')

        # Write current abundances
        for j in np.arange(len(headers) - 3):
            fout.write('%1.4e'%abundances[j][i] + ' ')
        fout.write('\n')

    # Close atm file
    fout.close()


def bestFit_tconfig(tconfig, date_dir):
  '''
  Write best-fit config file for best-fit Transit run
  '''
  # Open atmfile to read
  f = open(date_dir + tconfig, 'r')
  lines = np.asarray(f.readlines())
  f.close()

  # Change name to the atmfile in line zero
  atm_line = 'atm ' + date_dir + 'bestFit.atm' + '\n'
  lines[0] = atm_line

  # Write lines into the bestFit config file
  f = open(date_dir + 'bestFit_tconfig.cfg', 'w')
  f.writelines(lines)
  #f.writelines('savefiles yes')
  f.close()


def callTransit(atmfile, tepfile, MCfile, stepsize, molfit, solution,
                p0, tconfig, date_dir, params, burnin, abun_file):
    """
    Call Transit to produce best-fit outputs.
    Plot MCMC posterior PT plot.

    Parameters:
    -----------
    atmfile: String
       Atmospheric file.
    tepfile: String
       Transiting extra-solar planet file.
    MCfile: String
       File with MCMC log and best-fitting results.
    stepsize: 1D float ndarray
       FINDME
    molfit: 1D String ndarray
       List of molecule names to modify their abundances.
    solution: String
       Flag to indicate transit or eclipse geometry
    p0: Float
       Atmosphere's 'surface' pressure level.
    tconfig: String
       Transit  configuration file.
    date_dir: String
       Directory where to store results.
    params: 1D float ndarray
    burnin: Integer
    abun_file: String
       Elemental abundances file.
    """

    # read atmfile
    molecules, pressure, temp, abundances = mat.readatm(atmfile)

    # get surface gravity
    grav, Rp = mat.get_g(tepfile)

    # get star data
    R_star, T_star, sma, gstar = get_starData(tepfile)

    # get best parameters
    bestP, uncer, SN, mean = read_MCMC_out(MCfile)

    # get all params
    allParams = get_params(bestP, stepsize, params)

    # get PTparams and abundances factors
    nparams = len(allParams)
    nmol = len(molfit)
    nradfit = int(solution == 'transit')
    nPTparams = nparams - nmol - nradfit
    PTparams  = allParams[:nPTparams]

    # FINDME: Hardcoded value:
    T_int = 100  # K

    # call PT line profile to calculate temperature  --- LINE!!! Jasmina
    #best_T = pt.PT_line(pressure, PTparams, R_star, T_star, T_int,
    #                    sma, grav*1e2)

    # call PT madhu profile to calculate temperature --- MADHU!!! Jasmina
    # pressure must be decreasing so PT_inversion works!!!!!
    # othervise all the P-T profiles will be wrong and the code will not break!!!!
    if pressure[0]>pressure[1]: 
        # pressure goes -- large to small
        # reverse pressure -- small to large
        # get temp that corresponds to pressure -- small to large
        best_T = pt.PT_Inversion(pressure[::-1], PTparams)
    else:
        best_T = pt.PT_Inversion(pressure, PTparams)

    # Plot best PT profile
    plt.figure(1)
    plt.clf()
    # for Madhu if statement, will work for Line no problem
    if pressure[0]>pressure[1]:
        plt.semilogy(best_T, pressure[::-1], '-', color = 'r')
    else:
        plt.semilogy(best_T, pressure, '-', color = 'r')
    plt.xlim(0.9*min(best_T), 1.1*max(best_T))
    plt.ylim(max(pressure), min(pressure))
    plt.title('Best PT', fontsize=14)
    plt.xlabel('T [K]'     , fontsize=14)
    plt.ylabel('P [bar]', fontsize=14)
    # Save plot to current directory
    plt.savefig(date_dir + 'Best_PT.png') 

    # Update R0, if needed:
    if nradfit:
      Rp = allParams[nPTparams]
    # Mean molecular mass, be very careful these mu's correspond to
    # pressures -- large to small:
    mu  = mat.mean_molar_mass(abun_file, atmfile)



    # Re-calculate the layers' radii using the Hydrostatic-equilibrium calc:
    # (Has to be in reversed order since the interpolation requires the
    #  pressure array in increasing order, so in the radpress is reversed to
    # large to small!!!


    ###### Jasmina ONLY FOR MADHU, pressure must be decreasing so PT_inversion works!!!!!
    # othervise all the P-T profiles will be wrong and the code will not break!!!!
    if pressure[0]>pressure[1]:
        rad = mat.radpress(pressure[::-1], best_T, mu[::-1], p0, Rp, grav)
    else:
        rad = mat.radpress(pressure, best_T, mu, p0, Rp, grav)

    ###### FOR LINE ONLY Jasmina
    #rad = mat.radpress(pressure[::-1], best_T[::-1], mu[::-1], p0, Rp, grav)
    
    # reverse radius order so it correspond to pressure -- large to small
    rad = rad[::-1]


    # write best-fit atmospheric file Line Jasmina
    #write_atmfile(atmfile, molfit, rad, best_T, allParams[nPTparams+nradfit:], date_dir)

    # for Madhu Jasmina
    if pressure[0]>pressure[1]:
        write_atmfile(atmfile, molfit, rad, best_T[::-1], allParams[nPTparams+nradfit:],
                  date_dir)
    else:
       write_atmfile(atmfile, molfit, rad[::-1], best_T[::-1], allParams[nPTparams+nradfit:],
                  date_dir)

    # bestFit atm file
    bestFit_atm = date_dir + 'bestFit.atm'

    # write new bestFit Transit config
    bestFit_tconfig(tconfig, date_dir)

    # ========== plot MCMC PT profiles ==========

    # get MCMC data:
    MCMCdata = date_dir + "/output.npy"
    data = np.load(MCMCdata)
    nchains, npars, niter = np.shape(data)

    # stuck chains:
    data_stack = data[0,:,burnin:]
    for c in np.arange(1, nchains):
        data_stack = np.hstack((data_stack, data[c, :, burnin:]))

    # create array of PT profiles
    PTprofiles = np.zeros((np.shape(data_stack)[1], len(pressure)))

    # current PT parameters for each chain, iteration
    curr_PTparams = PTparams

    # fill-in PT profiles array
    print("  Plotting MCMC PT profile figure.")

    # open list for skipped profiles
    skipped = []
    for k in np.arange(0, np.shape(data_stack)[1]):
        j = 0
        for i in np.arange(len(PTparams)):
            if stepsize[i] != 0.0:
                curr_PTparams[i] = data_stack[j,k]
                j +=1
            else:
                pass
        ###### ONLY FOR LINE Jasmina
        #PTprofiles[k] = pt.PT_line(pressure, curr_PTparams, R_star, T_star,
        #                           T_int, sma, grav*1e2)

        ###### Jasmina ONLY FOR MADHU, pressure must be decreasing so PT_inversion works!!!!!
        # othervise all the P-T profiles will be wrong and the code will not break!!!!
        if pressure[0]>pressure[1]:
            # write into a temporary variable so you can catch skipped onse with
            # more layers than 100
            # must use increasing order to properly calculate PT inversion Jasmina Madhu -- small to large
            temp = pt.PT_Inversion(pressure[::-1], curr_PTparams)
            if len(temp) !=100:
                skipped = np.append(skipped, k)
                pass
            else:
                PTprofiles[k] = temp
                # must return to the decreasing order (large to small) so it can calculate fill_betweenx
                PTprofiles[k] = PTprofiles[k][::-1]
        else:
            # write into a temporary variable so you can catch skipped ones with
            # more layers than 100
            # already the array in in increasing order to properly calculate PT inversion Jasmina Madhu -- small to large
            temp = pt.PT_Inversion(pressure, curr_PTparams)
            if len(temp) !=100:
                skipped = np.append(skipped, k)
                pass
            else:
                PTprofiles[k] = temp
                # must return to the decreasing order (large to small) so it can calculate fill_betweenx
                PTprofiles[k] = PTprofiles[k][::-1]

    print 'Skipped profiles are: ', skipped

    # get percentiles (for 1,2-sigma boundaries):
    low1 = np.percentile(PTprofiles, 16.0, axis=0)
    hi1  = np.percentile(PTprofiles, 84.0, axis=0)
    low2 = np.percentile(PTprofiles,  2.5, axis=0)
    hi2  = np.percentile(PTprofiles, 97.5, axis=0)
    median = np.median(PTprofiles, axis=0)

    # plot figure
    plt.figure(2)
    plt.clf()
    ax=plt.subplot(111)
    ax.fill_betweenx(pressure, low2, hi2, facecolor="#62B1FF", edgecolor="0.5")
    ax.fill_betweenx(pressure, low1, hi1, facecolor="#1873CC",
                                                           edgecolor="#1873CC")
    plt.semilogy(median, pressure, "-", lw=2, label='Median',color="k")

    # for Madhu Jasmina
    if pressure[0]>pressure[1]:
        plt.semilogy(best_T, pressure[::-1], "-", lw=2, label="Best fit", color="r")
    else:
        plt.semilogy(best_T, pressure, "-", lw=2, label="Best fit", color="r")

    # for Line Jasmina 
    #plt.semilogy(best_T, pressure, "-", lw=2, label="Best fit", color="r") 
    plt.ylim(np.max(pressure), np.min(pressure))
    plt.legend(loc="best")
    plt.xlabel("Temperature  (K)", size=15)
    plt.ylabel("Pressure  (bar)",  size=15)

    # save figure
    savefile = date_dir + "MCMC_PTprofiles.png" 
    plt.savefig(savefile)



def plot_bestFit_Spectrum(filters, kurucz, tepfile, solution, output, data,
                                                          uncert, date_dir):
    '''
    Plot BART best-model spectrum
    '''
    # get star data
    R_star, T_star, sma, gstar = get_starData(tepfile)

    # get surface gravity
    grav, Rp = mat.get_g(tepfile)

    # convert Rp to m
    Rp = Rp * 1000

    # ratio planet to star
    rprs = Rp/R_star
  
    # read kurucz file
    starfl, starwn, tmodel, gmodel = w.readkurucz(kurucz, T_star, gstar)

    # read best-fit spectrum output file, take wn and spectra values
    if solution == 'eclipse':
        specwn, bestspectrum = rt.readspectrum(date_dir + output, wn=True)
        # print on screen
        print("  Plotting BART best-fit eclipse spectrum figure.")
    elif solution == 'transit':
        specwn, bestspectrum = rt.readspectrum(date_dir + output, wn=True)
        # print on screen
        print("  Plotting BART best-fit modulation spectrum figure.")

    # convert wn to wl
    specwl = 1e4/specwn

    # number of filters
    nfilters = len(filters)

    # read and resample the filters:
    nifilter  = [] # Normalized interpolated filter
    istarfl   = [] # interpolated stellar flux
    wnindices = [] # wavenumber indices used in interpolation
    meanwn    = [] # Filter mean wavenumber
    for i in np.arange(nfilters):
        # read filter:
        filtwaven, filttransm = w.readfilter(filters[i])
        meanwn.append(np.sum(filtwaven*filttransm)/sum(filttransm))
        # resample filter and stellar spectrum:
        nifilt, strfl, wnind = w.resample(specwn, filtwaven, filttransm,
                                            starwn,    starfl)
        nifilter.append(nifilt)
        istarfl.append(strfl)
        wnindices.append(wnind)

    # convert mean wn to mean wl
    meanwl = 1e4/np.asarray(meanwn)

    # band-integrate the flux-ratio or modulation:
    bandflux = np.zeros(nfilters, dtype='d')
    bandmod  = np.zeros(nfilters, dtype='d')
    for i in np.arange(nfilters):
        fluxrat = (bestspectrum[wnindices[i]]/istarfl[i]) * rprs*rprs
        bandflux[i] = w.bandintegrate(fluxrat, specwn, nifilter[i],
                                                                 wnindices[i])
        bandmod[i]  = w.bandintegrate(bestspectrum[wnindices[i]],
                                            specwn, nifilter[i], wnindices[i])

    # stellar spectrum on specwn:
    sinterp = si.interp1d(starwn, starfl)
    sflux = sinterp(specwn)
    frat = bestspectrum/sflux * rprs * rprs

    # plot figure
    plt.rcParams["mathtext.default"] = 'rm'
    matplotlib.rcParams.update({'mathtext.default':'rm'})
    matplotlib.rcParams.update({'font.size':10})
    plt.figure(3, (8.5, 5))
    plt.clf()

    # depending on solution plot eclipse or modulation spectrum
    if solution == 'eclipse':
        gfrat = gaussf(frat, 2)
        plt.semilogx(specwl, frat*1e3, "b", lw=1.5, label="Best-fit")
        #plt.semilogx(specwl, gfrat*1e3, "b", lw=1.5, label="Best-fit")
        plt.errorbar(meanwl, data*1e3, uncert*1e3, fmt="r.", label="data")
        plt.plot(meanwl, bandflux*1e3, "k.", label="model", alpha=1.0)
        plt.ylabel(r"$F_p/F_s$ (10$^{3}$)", fontsize=12)

    elif solution == 'transit':
        gmodel = gaussf(bestspectrum, 2)
        plt.semilogx(specwl, gmodel, "b", lw=1.5, label="Best-fit")
        # Check units!
        plt.errorbar(meanwl, data, uncert, fmt="or", label="data")
        plt.plot(meanwl, bandmod, "ok", label="model", alpha=0.5)
        plt.ylabel(r"$(R_p/R_s)^2$", fontsize=12)

    leg = plt.legend(loc="lower right")
    leg.get_frame().set_alpha(0.5)
    ax = plt.subplot(111)
    ax.set_xscale('log')
    plt.xlabel(r"${\rm Wavelength\ \ (um)}$", fontsize=12)  
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xticks(np.arange(min(specwl),max(specwl),1))
    plt.xlim(min(specwl),max(specwl))
    plt.savefig(date_dir + "BART-bestFit-Spectrum.png")

