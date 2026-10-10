// Words for the action heads and their options (contracts/actions.yaml uses identifiers).
import { titleCase } from "@/lib/format";

export const HEAD_LABEL: Record<string, string> = {
  priority_rule: "Queue priority",
  overflow_bays: "Overflow bays",
  divert: "Ambulance diversion",
  call_in: "Call in staff",
  fast_track: "Fast track",
  provider_split: "Provider focus",
  md_day: "Providers · day",
  md_evening: "Providers · evening",
  md_night: "Providers · night",
  rn_day: "Nurses · day",
  rn_evening: "Nurses · evening",
  rn_night: "Nurses · night",
  triage_nurses: "Triage stations",
  admission_cap: "Admission cap",
  discharge_push: "Discharge rounds",
  agency_contract: "Agency nurses",
  imaging_hours: "Imaging hours",
  bays_delta: "Treatment bays",
  ward_beds_delta: "Ward beds",
  equipment_buy: "Buy equipment",
  relocate: "Relocate a zone",
  headcount: "Permanent headcount",
};

const OPTION: Record<string, string> = { fcfs: "First come", acuity_first: "Acuity first", acuity_with_aging: "Acuity + waiting time", shortest_first: "Shortest first", one_rn: "One nurse", two_rn: "Two nurses", one_provider: "One provider", provider_and_rn: "Provider + nurse", ct: "CT scanner", xray: "X-ray unit", favor_new: "New patients", favor_dispositions: "Dispositions" };
export const optLabel = (o: string) => (/^lvl\d+$/.test(o) ? `Level ${o.slice(3)}` : (OPTION[o] ?? titleCase(o)));
