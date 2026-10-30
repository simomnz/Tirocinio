# Preparazione e pulizia a ogni scenario.

import os
import shutil
import tempfile


# le etichette si confrontano minuscole: @Manual non corrispondeva a "manual",
# quindi veniva eseguito come se fosse un criterio automatico, e il resoconto
# lo contava invece fra quelli da verificare a mano
def is_manual(scenario):
    return "manual" in [tag.lower() for tag in scenario.tags]


def before_scenario(context, scenario):

    # I criteri marcati @manual non si eseguono, li verifica il Product Owner

    if is_manual(scenario):
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
    
    if is_manual(scenario):
        return                  #niente da toccare se manual

    os.chdir(context.previous)      #torniamo indietro alla cartella di prima
    shutil.rmtree(context.folder, ignore_errors=True)      #cancelliamo la cartella temporanea
