# -*- coding: utf-8 -*-
"""Salva a CasaMCMV_65m2 aberta como copia congelada de validacao
(CasaMCMV_65m2_VALIDACAO_<data>.rvt) e passa a trabalhar nela."""
import os, datetime
from pyrevit import revit, DB, forms
doc = revit.doc
if doc.Title != "CasaMCMV_65m2":
    forms.alert("Abra a CasaMCMV_65m2.rvt antes (aberto: {}).".format(doc.Title), exitscript=True)
if doc.IsModified:
    forms.alert("A CasaMCMV_65m2 tem alteracoes nao salvas. Salve ou descarte antes.", exitscript=True)
destino = os.path.join(os.path.dirname(doc.PathName), "CasaMCMV_65m2_VALIDACAO_{}.rvt".format(datetime.date.today().isoformat()))
if os.path.exists(destino):
    forms.alert("Ja existe {}.".format(destino), exitscript=True)
opt = DB.SaveAsOptions()
opt.OverwriteExistingFile = False
doc.SaveAs(destino, opt)
forms.alert("Copia de validacao salva:\n{}".format(destino))
