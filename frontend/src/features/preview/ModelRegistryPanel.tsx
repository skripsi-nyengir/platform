import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Typography,
} from '@mui/material'
import { randomId } from '../../lib/id'
import { useState } from 'react'
import { publicDeviceId } from '../../contracts/common'
import type { ModelFamily } from '../../contracts/preview'
import { ApiErrorPanel } from '../../components/states/ApiErrorPanel'
import { PanelSkeleton } from '../../components/states/PanelSkeleton'
import { ProvenanceBadge } from '../../components/data/ProvenanceBadge'
import { useActivateModelMutation, useModelsQuery } from './queries'

export function ModelRegistryPanel() {
  const models = useModelsQuery(publicDeviceId)
  const activation = useActivateModelMutation(publicDeviceId)
  const [candidate, setCandidate] = useState<ModelFamily>()
  const candidateVersion = candidate?.versions[0]?.version

  return (
    <Stack component="section" aria-labelledby="registry-heading" spacing={2}>
      <Stack spacing={0.5}>
        <Typography id="registry-heading" variant="h2">Model registry</Typography>
        <Typography color="text.secondary">
          Tepat satu versi dipilih untuk replay berikutnya. Status artifact tidak memengaruhi
          simulator preview.
        </Typography>
      </Stack>
      {models.data === undefined ? (
        models.isError ? (
          <ApiErrorPanel error={models.error} onRetry={() => void models.refetch()} />
        ) : (
          <PanelSkeleton label="Loading model registry" />
        )
      ) : (
        <Stack spacing={1.5}>
          {models.data.families.map((family) => {
            const version = family.versions[0]
            if (version === undefined) return null
            const selected = version.version === models.data.active_model_version
            return (
              <Paper key={family.model_key} variant="outlined" sx={{ p: 2 }}>
                <Stack
                  direction="row"
                  spacing={2}
                  useFlexGap
                  sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}
                >
                  <Stack spacing={0.5}>
                    <Typography variant="h3">{family.display_name}</Typography>
                    <Typography variant="body2" color="text.secondary">{version.version}</Typography>
                  </Stack>
                  <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                    <Chip label={`Artifact ${family.artifact_status === 'pending' ? 'Pending' : 'Ready'}`} size="small" />
                    <ProvenanceBadge provenance={version.score_provenance} />
                    {selected ? <Chip label="Dipilih" color="primary" size="small" /> : (
                      <Button
                        size="small"
                        variant="outlined"
                        disabled={!version.selectable || !version.compatible}
                        onClick={() => setCandidate(family)}
                      >
                        Pilih model
                      </Button>
                    )}
                  </Stack>
                </Stack>
              </Paper>
            )
          })}
          {activation.isError ? <Alert severity="error">{activation.error.message}</Alert> : null}
        </Stack>
      )}
      <Dialog open={candidate !== undefined} onClose={() => setCandidate(undefined)}>
        <DialogTitle>Aktifkan {candidate?.display_name}</DialogTitle>
        <DialogContent>
          <Typography>
            Pilihan ini berlaku untuk replay berikutnya; job berjalan dan histori lama tidak berubah.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCandidate(undefined)}>Batal</Button>
          <Button
            variant="contained"
            disabled={activation.isPending || candidateVersion === undefined}
            onClick={() => {
              if (candidateVersion === undefined) return
              activation.mutate({
                command_id: randomId(),
                device_id: publicDeviceId,
                model_version: candidateVersion,
              }, { onSuccess: () => setCandidate(undefined) })
            }}
          >
            Aktifkan untuk replay berikutnya
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}
