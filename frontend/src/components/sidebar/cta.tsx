import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { Briefcase, ExternalLink } from 'lucide-react';
import { KortixProcessModal } from '@/components/sidebar/kortix-enterprise-modal';

export function CTACard() {
  return (
    <div className="rounded-lg bg-muted/30 dark:bg-muted/20 shadow-sm border border-border/50 p-3 transition-all">
      <div className="flex flex-col space-y-3">
        <div className="flex flex-col">
          <span className="text-sm font-medium text-foreground/90">
            Enterprise Demo
          </span>
          <span className="text-xs text-muted-foreground mt-0.5">
            AI employees for your company
          </span>
        </div>

        <div>
          {/* Keeping the KortixProcessModal as is, assuming its internal styling is independent or also theme-aware */}
          <KortixProcessModal />
        </div>

        <div className="flex items-center pt-2 border-t border-border/70 dark:border-border/50 mt-2">
          <Link
            href="https://www.kortix.ai/careers"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center text-xs text-muted-foreground hover:text-primary transition-colors group"
          >
            <Briefcase className="mr-1.5 h-3.5 w-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
            Join Our Team!
            <ExternalLink className="ml-1 h-3 w-3 text-muted-foreground group-hover:text-primary transition-colors" />
          </Link>
        </div>
      </div>
    </div>
  );
}
