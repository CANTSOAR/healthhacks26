// Which unfinished encounter holds a simulated patient. The server's patient route says a patient is held but not by
// which encounter, so the id is remembered in this tab when the encounter starts; when that is missing (another tab,
// storage cleared) the list of encounters is searched for the open one on that run and patient.
import { encApi } from "./api";

const KEY = (runId: string, patientId: number | string) => `hg.enc.open.${runId}.${patientId}`;

export function rememberOpenEncounter(runId: string, patientId: number | string, encounterId: string) {
  try {
    window.sessionStorage.setItem(KEY(runId, patientId), encounterId);
  } catch {
    /* storage blocked: the list lookup still works */
  }
}
export function forgetOpenEncounter(runId: string, patientId: number | string) {
  try {
    window.sessionStorage.removeItem(KEY(runId, patientId));
  } catch {
    /* storage blocked */
  }
}

/** The id of the open encounter for this patient of this run, or null when none can be found. */
export async function findOpenEncounter(runId: string, patientId: number | string): Promise<string | null> {
  try {
    const id = window.sessionStorage.getItem(KEY(runId, patientId));
    if (id) return id;
  } catch {
    /* storage blocked */
  }
  try {
    const all = await encApi.encounters();
    const open = all.filter((e) => e.status !== "finished" && e.sim?.run_id === runId && String(e.sim?.patient_id) === String(patientId));
    // the most recently started one, if the patient was somehow started twice
    open.sort((a, b) => (Date.parse(b.started ?? "") || 0) - (Date.parse(a.started ?? "") || 0));
    return open[0]?.encounter_id ?? null;
  } catch {
    return null;
  }
}

/** Give a held patient back to the simulation's own sampler (the encounter stays on the server, unfinished). */
export async function giveBack(runId: string, patientId: number | string): Promise<boolean> {
  const r = (await encApi.releaseHold(runId, patientId)) as { released?: boolean } | undefined;
  forgetOpenEncounter(runId, patientId);
  return r?.released !== false;
}
