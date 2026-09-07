use std::collections::BTreeMap;

use ai_ex_domain::{AppError, MemoryEntry, MemoryKind, MemoryPage, MemoryRequest, MemoryResponse};

#[cfg(test)]
#[path = "memory_panel_tests.rs"]
mod tests;
#[path = "memory_panel_ui.rs"]
mod ui;

const PAGE_SIZE: usize = 12;

struct Pending {
    id: u64,
    mutation: bool,
    clear_draft: bool,
}

#[derive(Default)]
pub struct MemoryPanel {
    profile_id: String,
    page: Option<MemoryPage>,
    query: String,
    kind: Option<MemoryKind>,
    draft: String,
    editing: Option<MemoryEntry>,
    forget: Option<MemoryEntry>,
    drafts: BTreeMap<String, (String, Option<MemoryEntry>)>,
    pending: Option<Pending>,
    next_id: u64,
    loaded: bool,
    feedback: Option<String>,
    requires_review: bool,
    focus_editor: bool,
    offsets: Vec<usize>,
}

impl MemoryPanel {
    pub fn set_profile(&mut self, profile_id: &str) {
        if self.profile_id == profile_id {
            return;
        }
        if !self.draft.is_empty() {
            self.drafts.insert(
                self.profile_id.clone(),
                (std::mem::take(&mut self.draft), self.editing.take()),
            );
        }
        let (draft, editing) = self.drafts.remove(profile_id).unwrap_or_default();
        self.profile_id = profile_id.to_owned();
        self.draft = draft;
        self.editing = editing;
        self.forget = None;
        self.page = None;
        self.query.clear();
        self.kind = None;
        self.loaded = false;
        self.pending = None;
        self.feedback = None;
        self.requires_review = false;
        self.focus_editor = false;
        self.offsets.clear();
    }

    pub fn mutation_pending(&self) -> bool {
        self.pending.as_ref().is_some_and(|item| item.mutation)
    }

    pub fn has_unsaved(&self) -> bool {
        !self.draft.is_empty() || !self.drafts.is_empty() || self.mutation_pending()
    }

    pub fn begin(&mut self, request: MemoryRequest) -> Option<crate::worker::WorkerCommand> {
        let mutation = request.is_mutation();
        if self.pending.is_some() || (mutation && self.requires_review) {
            return None;
        }
        if request.profile_id() != self.profile_id || request.validate().is_err() {
            self.feedback = Some("请检查记忆内容与当前角色后重试。".to_owned());
            return None;
        }
        self.next_id = self.next_id.wrapping_add(1);
        let clear_draft = matches!(
            request,
            MemoryRequest::Remember { .. } | MemoryRequest::Correct { .. }
        );
        self.pending = Some(Pending {
            id: self.next_id,
            mutation,
            clear_draft,
        });
        self.loaded = true;
        self.feedback = None;
        Some(crate::worker::WorkerCommand::Memory {
            request_id: self.next_id,
            request,
        })
    }

    pub fn receive(&mut self, request_id: u64, result: Result<MemoryResponse, AppError>) -> bool {
        if self
            .pending
            .as_ref()
            .is_none_or(|item| item.id != request_id)
        {
            return false;
        }
        let pending = self.pending.take().expect("matching request");
        match result {
            Ok(MemoryResponse::Page(page))
                if !pending.mutation && page.profile_id == self.profile_id =>
            {
                if page.offset == 0 {
                    self.offsets.clear();
                } else if let Some(index) = self
                    .offsets
                    .iter()
                    .position(|offset| *offset == page.offset)
                {
                    self.offsets.truncate(index);
                }
                self.offsets.push(page.offset);
                self.page = Some(page);
                self.feedback = None;
                self.requires_review = false;
            }
            Ok(MemoryResponse::Changed) if pending.mutation => {
                if pending.clear_draft {
                    self.draft.clear();
                    self.editing = None;
                }
                self.forget = None;
                self.page = None;
                self.loaded = false;
                self.feedback = Some("记忆已更新，下一轮对话会使用新的内容。".to_owned());
                return true;
            }
            Ok(_) => {
                self.requires_review |= pending.mutation;
                self.feedback = Some("记忆响应与当前操作不一致，请刷新后核对。".to_owned());
            }
            Err(error) => {
                let uncertain = pending.mutation
                    && matches!(
                        error.kind,
                        ai_ex_domain::ErrorKind::Connectivity
                            | ai_ex_domain::ErrorKind::Protocol
                            | ai_ex_domain::ErrorKind::Internal
                    );
                self.requires_review |= uncertain;
                if uncertain {
                    self.query.clear();
                    self.kind = None;
                    self.page = None;
                }
                let hint = if uncertain {
                    "操作结果尚未确认，草稿已保留。请先刷新核对，避免重复记住。"
                } else {
                    "操作未完成，草稿已保留。结束当前回复后可刷新或重试。"
                };
                self.feedback = Some(format!("{hint}\n{error}"));
            }
        }
        false
    }

    fn list_request(&self, offset: usize) -> MemoryRequest {
        MemoryRequest::List {
            profile_id: self.profile_id.clone(),
            query: self.query.trim().to_owned(),
            kind: self.kind,
            offset,
            limit: PAGE_SIZE,
        }
    }

    fn previous_offset(&self) -> usize {
        self.offsets.iter().rev().nth(1).copied().unwrap_or(0)
    }
}
