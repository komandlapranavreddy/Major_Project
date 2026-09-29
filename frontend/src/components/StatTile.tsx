import { motion } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { easeOut, panelSurface } from '@/lib/design';
import { cn } from '@/lib/utils';

export function StatTile({
  index,
  label,
  value,
  sublabel,
}: {
  index: number;
  label: string;
  value: string;
  sublabel?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: easeOut, delay: index * 0.05 }}
    >
      <Card className={cn('p-4', panelSurface)}>
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="mt-1.5 text-3xl font-semibold">{value}</p>
        {sublabel && <p className="mt-1 text-xs text-muted-foreground">{sublabel}</p>}
      </Card>
    </motion.div>
  );
}
