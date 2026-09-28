import * as Dialog from "@radix-ui/react-dialog";
import { Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "./Button";

export function DeleteWorkspaceDialog({ workspace, onDelete, location }: {
  workspace: { workspace_id: string; name: string };
  onDelete: (workspaceId: string) => void;
  location?: "browser" | "authority";
}) {
  const [open, setOpen] = useState(false);
  // Bind acknowledgment to the exact subject and storage boundary being removed.
  const subject = JSON.stringify([workspace.workspace_id, workspace.name, location]);
  const [acknowledgedSubject, setAcknowledgedSubject] = useState<string | null>(null);
  const acknowledged = acknowledgedSubject === subject;
  useEffect(() => setAcknowledgedSubject(null), [subject]);
  const changeOpen = (next: boolean) => {
    setAcknowledgedSubject(null);
    setOpen(next);
  };
  return (
    <Dialog.Root open={open} onOpenChange={changeOpen}>
      <Dialog.Trigger asChild>
        <Button variant="ghost"><Trash2 className="h-4 w-4" aria-hidden="true" />Delete workspace</Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-fg1/50" />
        <Dialog.Content className="surface fixed left-1/2 top-1/2 z-50 max-h-dvh w-11/12 max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-lg font-semibold text-fg1">Delete workspace?</Dialog.Title>
              <Dialog.Description className="mt-2 text-sm text-fg2">
                {location === "authority"
                  ? <>Request removal of the workspace record for {workspace.name} from tenant-scoped authority storage. Removal depends on the authority accepting and saving the request.</>
                  : <>Remove the saved evaluation draft for {workspace.name} from this browser’s workspace list. This does not remove an enterprise authority workspace.</>}
              </Dialog.Description>
            </div>
            <Dialog.Close asChild><Button variant="ghost" aria-label="Close deletion dialog"><X className="h-4 w-4" aria-hidden="true" /></Button></Dialog.Close>
          </div>
          <div className="mt-4 text-sm text-fg2">
            <p className="font-semibold text-fg1">Records outside this removal</p>
            <ul className="mt-2 list-disc space-y-2 pl-5">
              <li>Release proof packs, audit events, connector evidence and governed execution records are retained separately.</li>
              <li>Downloaded exports, other browser copies or caches, backups and provider records are not erased by this action.</li>
            </ul>
            <p className="mt-3">This is not a data-erasure request. Ask your organization’s data or records owner to review retention, legal holds, derivative deletion and restore behavior. Export only when your approved records policy permits it.</p>
          </div>
          <label className="mt-4 flex items-start gap-2 text-sm text-fg1">
            <input type="checkbox" className="mt-1" checked={acknowledged} onChange={(event) => setAcknowledgedSubject(event.target.checked ? subject : null)} />
            <span>I understand that related records and copies are not erased.</span>
          </label>
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Dialog.Close asChild><Button>Cancel</Button></Dialog.Close>
            <Button variant="danger" disabled={!acknowledged} onClick={() => {
              if (!acknowledged) return;
              onDelete(workspace.workspace_id);
              changeOpen(false);
            }}><Trash2 className="h-4 w-4" aria-hidden="true" />Remove workspace record</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
