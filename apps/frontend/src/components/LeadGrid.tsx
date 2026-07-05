import { motion } from 'framer-motion'
import { LeadCard, type Lead } from './LeadCard'

interface LeadGridProps {
  leads: Lead[]
}

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.08,
    },
  },
}

const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
}

export function LeadGrid({ leads }: LeadGridProps) {
  if (leads.length === 0) return null

  return (
    <motion.div
      data-testid="lead-grid"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      style={{
        display: 'grid',
        gap: '16px',
        gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 320px), 1fr))',
      }}
    >
      {leads.map((lead, idx) => (
        <motion.div key={`${lead.company}-${idx}`} variants={cardVariants}>
          <LeadCard lead={lead} />
        </motion.div>
      ))}
    </motion.div>
  )
}
