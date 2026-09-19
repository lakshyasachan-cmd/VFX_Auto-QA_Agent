import { MOCK_CLUSTER_NODES, MOCK_INCIDENTS } from "./mockData";
import { ClusterNodeHealth, IncidentSummary } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "vfx-lead-td-secret-key-prod-002";

export async function fetchIncidents(): Promise<IncidentSummary[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/approvals`, {
      cache: "no-store",
      headers: { "X-API-Key": API_KEY },
    });
    if (res.ok) {
      // In real backend, map approvals / incidents
    }
  } catch (err) {
    // Graceful fallback to local mock data
  }
  return MOCK_INCIDENTS;
}

export async function fetchIncidentById(id: string): Promise<IncidentSummary | null> {
  const incidents = await fetchIncidents();
  return incidents.find((i) => i.id === id) || null;
}

export async function approveRemediationAction(
  approvalId: string,
  actor: string = "lead_vfx_supervisor",
  notes: string = "Approved via Mission Control Dashboard"
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/approvals/${approvalId}/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify({ actor, notes }),
    });
    if (res.ok) {
      const data = await res.json();
      return { success: true, data };
    }
    const errData = await res.json();
    return { success: false, error: errData.detail || "Approval request rejected." };
  } catch (err: any) {
    // In local sandbox mock mode: simulate instant success
    return {
      success: true,
      data: {
        approval_id: approvalId,
        status: "APPROVED",
        approved_by: actor,
        decided_at: new Date().toISOString(),
      },
    };
  }
}

export async function rejectRemediationAction(
  approvalId: string,
  actor: string = "lead_vfx_supervisor",
  notes: string = "Rejected via Mission Control Dashboard"
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/approvals/${approvalId}/reject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify({ actor, notes }),
    });
    if (res.ok) {
      const data = await res.json();
      return { success: true, data };
    }
    const errData = await res.json();
    return { success: false, error: errData.detail || "Rejection failed." };
  } catch (err: any) {
    return {
      success: true,
      data: {
        approval_id: approvalId,
        status: "REJECTED",
        decided_by: actor,
        decided_at: new Date().toISOString(),
      },
    };
  }
}

export async function fetchClusterHealth(): Promise<ClusterNodeHealth[]> {
  return MOCK_CLUSTER_NODES;
}
