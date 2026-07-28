/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_LOOPOS_AUTHORITY_URL?: string;
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
