import { useCallback } from 'react'
import { Stack, Inline, ProgressBar } from '@ui/atoms'
import { ModuleLayout } from '@/components/ModuleLayout'
import { IntakeContextProvider, useIntake } from './IntakeContext'

import { Step1Municipality } from './steps/Step1Municipality'
import { Step2Details } from './steps/Step2Details'
import { Step3Financials } from './steps/Step3Financials'
import { Step4Options } from './steps/Step4Options'
import { Step5Review } from './steps/Step5Review'

const STEPS = [
  { number: 1, title: 'Municipality', component: Step1Municipality },
  { number: 2, title: 'Details', component: Step2Details },
  { number: 3, title: 'Financials', component: Step3Financials },
  { number: 4, title: 'Options', component: Step4Options },
  { number: 5, title: 'Review', component: Step5Review },
]

function WizardContent() {
  const { step, setStep } = useIntake()

  const handleNext = useCallback(() => {
    setStep(Math.min(5, step + 1))
  }, [step, setStep])

  const handleBack = useCallback(() => {
    setStep(Math.max(1, step - 1))
  }, [step, setStep])

  const progress = (step / STEPS.length) * 100
  const CurrentStep = STEPS[step - 1].component

  return (
    <Stack className="h-full bg-ws-bg" gap="none">
      {/* Wizard Header */}
      <div className="bg-ws-panel-bg border-b border-ws-panel-border px-6 py-4">
        <Stack gap="sm">
          <Inline align="center" justify="between">
            <h1 className="text-lg font-semibold text-ws-fg">New BFA Project</h1>
            <span className="text-sm text-ws-text-secondary">
              Step {step} of {STEPS.length}: {STEPS[step - 1].title}
            </span>
          </Inline>
          <ProgressBar value={progress} size="sm" />
        </Stack>
      </div>

      {/* Step Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-2xl">
          <CurrentStep onNext={handleNext} onBack={handleBack} />
        </div>
      </div>
    </Stack>
  )
}

export function IntakePage() {
  return (
    <ModuleLayout module="projects" activePage="new">
      <IntakeContextProvider>
        <WizardContent />
      </IntakeContextProvider>
    </ModuleLayout>
  )
}
