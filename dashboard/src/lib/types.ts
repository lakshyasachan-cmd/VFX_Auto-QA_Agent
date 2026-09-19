export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
export type IncidentStatus = "OPEN" | "INVESTIGATING" | "REMEDIATING" | "AWAITING_APPROVAL" | "RESOLVED" | "CLOSED";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface VFXEntity {
  entity_type: string;
  entity_id: string;
  project?: string;
  sequence?: string;
  shot?: string;
  asset_name?: string;
  job_id?: string;
  node_name?: string;
}

export interface IncidentEvidenceItem {
  id: string;
  evidence_type: "RENDER_LOG" | "NODE_TELEMETRY" | "USD_DEPENDENCY" | "FRAME_QC";
  source: string;
  title: string;
  raw_content?: string;
  structured_data: Record<string, any>;
  captured_at: string;
}

export interface AgentFindingItem {
  id: string;
  agent_name: string;
  finding_type: string;
  severity: Severity;
  confidence: number;
  title: string;
  description: string;
  structured_payload?: Record<string, any>;
}

export interface AgentRunItem {
  id: string;
  agent_name: string;
  agent_type: "SUPERVISOR" | "RENDER_QA" | "HARDWARE" | "ASSET" | "HISTORICAL" | "REMEDIATION";
  status: "RUNNING" | "COMPLETED" | "FAILED";
  started_at: string;
  completed_at?: string;
  output_summary?: string;
  findings: AgentFindingItem[];
}

export interface ReasoningResultItem {
  id: string;
  root_cause: string;
  confidence: number;
  severity: Severity;
  summary: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  alternative_causes: Array<{ cause: string; probability: number }>;
  recommended_action: string;
}

export interface RemediationActionItem {
  action: string;
  reason: string;
  risk: RiskLevel;
  confidence: number;
  requires_human_approval: boolean;
  parameters: Record<string, any>;
}

export interface RemediationPlanItem {
  id: string;
  strategy: string;
  risk_level: RiskLevel;
  status: string;
  requires_approval: boolean;
  rollback_strategy?: string;
  preventive_measures: string[];
  actions: RemediationActionItem[];
}

export interface ApprovalRequestItem {
  id: string;
  plan_id: string;
  action: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | "AUTO_APPROVED";
  risk: RiskLevel;
  confidence: number;
  requires_human_approval: boolean;
  requested_at: string;
  decided_at?: string;
  decided_by?: string;
  decision_reason?: string;
  parameters: Record<string, any>;
}

export interface ExecutionEventItem {
  id: string;
  tool_name: string;
  status: "SUCCESS" | "FAILED" | "QUEUED" | "RUNNING";
  parameters: Record<string, any>;
  result?: Record<string, any>;
  error?: string;
  executed_at: string;
  actor: string;
}

export interface IncidentSummary {
  id: string;
  correlation_id: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  event_type: string;
  source_system: string;
  project: string;
  sequence: string;
  shot: string;
  job_id?: string;
  node_id?: string;
  error_signature?: string;
  created_at: string;
  updated_at: string;
  evidence: IncidentEvidenceItem[];
  agent_runs: AgentRunItem[];
  reasoning?: ReasoningResultItem;
  remediation_plan?: RemediationPlanItem;
  approvals: ApprovalRequestItem[];
  executions: ExecutionEventItem[];
  precedents?: Array<{ title: string; resolution: string; success_rate: number; similarity: number }>;
}

export interface ClusterNodeHealth {
  node_id: string;
  status: "ONLINE" | "DEGRADED" | "OFFLINE" | "MAINTENANCE";
  gpu_utilization: number;
  gpu_memory_used_percent: number;
  gpu_temperature_celsius: number;
  cpu_utilization: number;
  scratch_disk_free_gb: number;
  active_jobs: number;
}
