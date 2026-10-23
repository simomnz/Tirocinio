# Preparazione e pulizia intorno a ogni scenario.

import os
import shutil
import tempfile


def before_scenario(context, scenario):
    # I criteri marcati @manual non si eseguono: li verifica il Product Owner
    if "manual" in scenario.tags:
        scenario.skip("to be checked by hand")
        return

    # Ogni scenario parte da una cartella vuota, cosi' i file creati da un
    # criterio non si vedono in quello dopo
    context.folder = tempfile.mkdtemp()
    context.previous = os.getcwd()
    os.chdir(context.folder)

    context.result = None
    context.error = None
    context.exit_code = None
    context.output = ""
    context.status = None
    context.body = ""
    context.duration = 0


def after_scenario(context, scenario):
    if "manual" in scenario.tags:
        return

    os.chdir(context.previous)
    shutil.rmtree(context.folder, ignore_errors=True)
