"use client";

import { useCallback, useEffect, useState } from "react";
import { TriangleAlert } from "lucide-react";
import {
  ApiError,
  getAgendamentos,
  getAutoScheduleConfig,
  getAutoScheduleStatus,
  getCardapio,
  saveAutoScheduleConfig,
} from "@/lib/api";
import type {
  Agendamento,
  AutoScheduleConfigResponse,
  AutoScheduleStatusResponse,
  DiaCardapio,
  MealCode,
  WeekdayCode,
} from "@/types";
import { useToast } from "./Toast";
import AutoScheduleDialog from "./AutoScheduleDialog";
import AutoScheduleMealSelector from "./AutoScheduleMealSelector";
import AutoScheduleStatusSummary from "./AutoScheduleStatusSummary";
import AutoScheduleTrigger from "./AutoScheduleTrigger";
import AutoScheduleWeekPreview from "./AutoScheduleWeekPreview";
import {
  buildRequest,
  cloneDraft,
  emptyDraft,
  getAutomationState,
  hasAnyWeeklyRule,
  selectionSummary,
  toggleWeeklyRule,
} from "./autoScheduleUi";

export default function AutoScheduleControl() {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<AutoScheduleStatusResponse | null>(null);
  const [savedConfig, setSavedConfig] = useState<AutoScheduleConfigResponse | null>(null);
  const [draft, setDraft] = useState<AutoScheduleConfigResponse>(emptyDraft());
  const [previewCardapio, setPreviewCardapio] = useState<DiaCardapio[]>([]);
  const [previewAgendamentos, setPreviewAgendamentos] = useState<Agendamento[]>([]);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [loadingDialog, setLoadingDialog] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [orbitalPassword, setOrbitalPassword] = useState("");
  const [clearSavedCredentials, setClearSavedCredentials] = useState(false);

  const loadStatus = useCallback(async (showLoader = false) => {
    if (showLoader) {
      setLoadingStatus(true);
    }

    try {
      const payload = await getAutoScheduleStatus();
      setStatus(payload);
      setError("");
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Nao foi possivel carregar o status da automacao.";
      setError(message);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  const loadDialogData = useCallback(async () => {
    setLoadingDialog(true);
    setLoadingPreview(true);
    setPreviewError("");

    const [configResult, statusResult, cardapioResult, agendamentosResult] =
      await Promise.allSettled([
        getAutoScheduleConfig(),
        getAutoScheduleStatus(),
        getCardapio(),
        getAgendamentos(),
      ]);

    let panelError = "";

    if (configResult.status === "fulfilled") {
      setSavedConfig(configResult.value);
      setDraft(cloneDraft(configResult.value));
      setOrbitalPassword("");
      setClearSavedCredentials(false);
    } else {
      panelError =
        configResult.reason instanceof ApiError
          ? configResult.reason.message
          : "Nao foi possivel carregar a configuracao da automacao.";
    }

    if (statusResult.status === "fulfilled") {
      setStatus(statusResult.value);
    } else if (!panelError) {
      panelError =
        statusResult.reason instanceof ApiError
          ? statusResult.reason.message
          : "Nao foi possivel carregar o status da automacao.";
    }

    if (cardapioResult.status === "fulfilled") {
      setPreviewCardapio(cardapioResult.value.semana);
    } else {
      setPreviewCardapio([]);
      setPreviewError("Nao foi possivel carregar o cardapio desta semana para a previa.");
    }

    if (agendamentosResult.status === "fulfilled") {
      setPreviewAgendamentos(agendamentosResult.value.agendamentos);
    } else {
      setPreviewAgendamentos([]);
      setPreviewError((current) =>
        current || "Nao foi possivel carregar os agendamentos atuais para a previa."
      );
    }

    if (panelError) {
      setError(panelError);
      toast(panelError, "error");
    } else {
      setError("");
    }

    setLoadingDialog(false);
    setLoadingPreview(false);
    setLoadingStatus(false);
  }, [toast]);

  useEffect(() => {
    void loadStatus(true);

    const interval = setInterval(() => {
      void loadStatus(false);
    }, 60000);

    return () => clearInterval(interval);
  }, [loadStatus]);

  const handleDismiss = useCallback(() => {
    setDraft(savedConfig ? cloneDraft(savedConfig) : emptyDraft());
    setError("");
    setPreviewError("");
    setOrbitalPassword("");
    setClearSavedCredentials(false);
    setOpen(false);
  }, [savedConfig]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        handleDismiss();
      }
    }

    window.addEventListener("keydown", handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleEscape);
    };
  }, [handleDismiss, open]);

  function handleToggleOpen() {
    if (open) {
      handleDismiss();
      return;
    }

    setOpen(true);
    void loadDialogData();
  }

  function toggleEnabled() {
    setDraft((current) => ({
      ...current,
      enabled: !current.enabled,
    }));
  }

  function toggleMeal(weekday: WeekdayCode, code: MealCode) {
    setDraft((current) => {
      return {
        ...current,
        weekly_rules: toggleWeeklyRule(current.weekly_rules, weekday, code),
      };
    });
  }

  async function handleSave() {
    if (draft.enabled && !hasAnyWeeklyRule(draft.weekly_rules)) {
      const message = "Selecione ao menos uma combinacao de dia e refeicao para ativar a automacao.";
      setError(message);
      toast(message, "error");
      return;
    }

    const normalizedPassword = orbitalPassword.trim();
    const hasPersistedCredentials = Boolean(
      savedConfig?.has_credentials ?? draft.has_credentials
    );
    const willClearCredentials = clearSavedCredentials && !normalizedPassword;
    const willHaveCredentials =
      Boolean(normalizedPassword) || (hasPersistedCredentials && !willClearCredentials);

    if (draft.enabled && !willHaveCredentials) {
      const message =
        "Informe a senha do Orbital para ativar a automacao deste usuario.";
      setError(message);
      toast(message, "error");
      return;
    }

    setSaving(true);

    try {
      const response = await saveAutoScheduleConfig(
        buildRequest(draft, normalizedPassword, clearSavedCredentials)
      );
      setSavedConfig(response);
      setDraft(cloneDraft(response));
      setOrbitalPassword("");
      setClearSavedCredentials(false);
      await loadStatus(false);
      setOpen(false);
      setError("");
      toast("Automacao atualizada.", "success");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Nao foi possivel salvar a automacao.";
      setError(message);
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  }

  const automationState = getAutomationState(status);
  const hasUnsavedToggleChange =
    savedConfig !== null && savedConfig.enabled !== draft.enabled;
  const footerSummary = selectionSummary(draft.enabled, draft.weekly_rules);
  const hasPersistedCredentials = Boolean(
    savedConfig?.has_credentials ?? draft.has_credentials
  );
  const normalizedPassword = orbitalPassword.trim();
  const willClearCredentials = clearSavedCredentials && !normalizedPassword;
  const credentialReady =
    Boolean(normalizedPassword) || (hasPersistedCredentials && !willClearCredentials);
  const saveDisabled =
    loadingDialog ||
    saving ||
    (draft.enabled && !hasAnyWeeklyRule(draft.weekly_rules)) ||
    (draft.enabled && !credentialReady);

  return (
    <>
      <AutoScheduleTrigger
        active={automationState.active}
        expired={automationState.expired}
        loading={loadingStatus}
        open={open}
        onClick={handleToggleOpen}
      />

      <AutoScheduleDialog
        open={open}
        loading={loadingDialog}
        saving={saving}
        saveDisabled={saveDisabled}
        footerSummary={footerSummary}
        onClose={handleDismiss}
        onSave={handleSave}
      >
        <div className="space-y-6">
          {status && !status.has_credentials ? (
            <div className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <p>Salve a senha do Orbital deste usuario para permitir execucoes automaticas mesmo sem sessao web ativa.</p>
            </div>
          ) : null}

          {error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <AutoScheduleStatusSummary
            draft={draft}
            status={status}
            loading={loadingStatus}
            hasUnsavedToggleChange={hasUnsavedToggleChange}
            onToggleEnabled={toggleEnabled}
          />

          <section className="space-y-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Credencial da automacao</h3>
                <p className="text-sm text-slate-500">
                  Essa senha fica vinculada ao seu usuario e permite que o agendamento rode sozinho no servidor.
                </p>
              </div>

              <span
                className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-semibold ${
                  credentialReady
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {credentialReady ? "Senha pronta" : "Senha pendente"}
              </span>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <label
                htmlFor="auto-schedule-password"
                className="text-sm font-semibold text-slate-900"
              >
                Senha do Orbital
              </label>
              <input
                id="auto-schedule-password"
                type="password"
                value={orbitalPassword}
                onChange={(event) => {
                  const value = event.target.value;
                  setOrbitalPassword(value);
                  if (value.trim()) {
                    setClearSavedCredentials(false);
                  }
                }}
                autoComplete="current-password"
                placeholder={
                  hasPersistedCredentials && !clearSavedCredentials
                    ? "Deixe em branco para manter a senha salva atual"
                    : "Digite a senha usada no Orbital"
                }
                className="mt-3 w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition-colors focus:border-[#006633] focus:ring-2 focus:ring-[#006633]/15"
              />
              <p className="mt-2 text-xs text-slate-500">
                A senha e armazenada de forma criptografada no servidor e so e usada para a automacao deste usuario.
              </p>

              {hasPersistedCredentials ? (
                <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-slate-600">
                      {clearSavedCredentials && !normalizedPassword
                        ? "A senha salva sera removida quando voce salvar."
                        : "Ja existe uma senha salva para esta conta. Informe outra apenas se quiser atualizar."}
                    </p>

                    <button
                      type="button"
                      onClick={() =>
                        setClearSavedCredentials((current) => !current)
                      }
                      className={`rounded-xl px-3 py-2 text-sm font-medium transition-colors ${
                        clearSavedCredentials && !normalizedPassword
                          ? "bg-slate-900 text-white hover:bg-slate-800"
                          : "bg-white text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      {clearSavedCredentials && !normalizedPassword
                        ? "Manter senha salva"
                        : "Remover senha salva"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  Nenhuma senha salva ainda. Para rodar automaticamente no servidor, cada usuario precisa salvar a propria senha do Orbital.
                </div>
              )}
            </div>
          </section>

          <AutoScheduleMealSelector
            weeklyRules={draft.weekly_rules}
            durationMode={draft.duration_mode}
            onToggleMeal={toggleMeal}
            onSelectDuration={(value) =>
              setDraft((current) => ({
                ...current,
                duration_mode: value,
              }))
            }
          />

          <AutoScheduleWeekPreview
            cardapio={previewCardapio}
            agendamentos={previewAgendamentos}
            weeklyRules={draft.weekly_rules}
            loading={loadingPreview}
            error={previewError}
          />
        </div>
      </AutoScheduleDialog>
    </>
  );
}
