# Preparazione e pulizia a ogni scenario.

import os
import shutil
import tempfile


def before_scenario(context, scenario):
    
    # I criteri marcati @manual non si eseguono, li verifica il Product Owner
    
    if "manual" in scenario.tags:
        scenario.skip("to be checked by hand")      
        return                  # se manual non prepariamo lo scenario, non serve

    # Ogni scenario ha una cartella vuota dedicata, cosi' i file creati da un criterio non si vedono in quello dopo
    context.folder = tempfile.mkdtemp()     # cartela con nome random
    context.previous = os.getcwd()      #salviamo dove eravamo prima di cambiare cartella         
    os.chdir(context.folder)        #cambiamo cartella

    # possibili risultati
    context.result = None
    context.error = None
    context.exit_code = None
    context.output = ""
    context.status = None
    context.body = ""
    context.duration = 0


def after_scenario(context, scenario):
    
    if "manual" in scenario.tags:
        return                  #niente da toccare se manual

    os.chdir(context.previous)      #torniamo indietro alla cartella di prima
    shutil.rmtree(context.folder, ignore_errors=True)      #cancelliamo la cartella temporanea
