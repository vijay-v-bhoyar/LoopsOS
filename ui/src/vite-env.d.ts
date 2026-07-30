/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LOOPOS_AUTHORITY_URL?: string;
  readonly VITE_LOOPOS_DEPLOYMENT_MODE?: "evaluation" | "enterprise";
  readonly VITE_LOOPOS_ENVIRONMENT_NAME?: string;
  readonly VITE_LOOPOS_AUTH_MODE?: string;
  readonly VITE_LOOPOS_PERSISTENCE_MODE?: string;
  readonly VITE_LOOPOS_AUDIT_MODE?: string;
  readonly VITE_LOOPOS_RETENTION_POLICY_URL?: string;
  readonly VITE_LOOPOS_SUPPORT_CONTACT?: string;
  readonly VITE_LOOPOS_OUTBOUND_POLICY_MODE?: "allowlist" | "deny_all";
  readonly VITE_LOOPOS_ALLOWED_ENDPOINT_HOSTS?: string;
  readonly VITE_LOOPOS_BACKUP_RESTORE_EVIDENCE_URL?: string;
}

declare module "mammoth/mammoth.browser" {
  const mammoth: {
    extractRawText(options: { arrayBuffer: ArrayBuffer }): Promise<{
      value: string;
      messages: Array<{ type?: string; message: string }>;
    }>;
  };
  export default mammoth;
}
