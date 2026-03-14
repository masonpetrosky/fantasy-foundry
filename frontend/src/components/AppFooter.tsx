import React from "react";
import { NewsletterSignup } from "../NewsletterSignup";

export interface AppFooterProps {
  meta: Record<string, unknown> | null;
  buildLabel: string;
  apiBase: string;
}

export const AppFooter = React.memo(function AppFooter({
  meta,
  buildLabel,
  apiBase,
}: AppFooterProps): React.ReactElement {
  return (
    <footer>
      <div className="footer-inner">
        <div>
          {meta?.last_projection_update
            ? <>Projections updated {meta.last_projection_update as string}.</>
            : <>Projections updated as-needed.</>
          }
          {buildLabel && <span className="build-id">Build {buildLabel}</span>}
        </div>
        <NewsletterSignup apiBase={apiBase} />
      </div>
    </footer>
  );
});
