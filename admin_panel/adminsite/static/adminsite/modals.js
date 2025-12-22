function createElement(html) {
    const tpl = document.createElement('template');
    tpl.innerHTML = html.trim();
    return tpl.content.firstElementChild;
}

class BaseModal {
    constructor(title) {
        this.backdrop = createElement('<div class="modal-backdrop" hidden></div>');
        this.modal = createElement('<div class="modal"></div>');
        this.title = title;
        this.status = createElement('<div class="status"></div>');
        const header = createElement('<header><h3></h3></header>');
        header.querySelector('h3').textContent = title;
        this.modal.appendChild(header);
        this.modal.appendChild(this.status);
        this.backdrop.appendChild(this.modal);
        document.body.appendChild(this.backdrop);
    }

    showMessage(text, isError = false) {
        this.status.textContent = text || '';
        this.status.classList.toggle('error', Boolean(text && isError));
        this.status.classList.toggle('success', Boolean(text && !isError));
    }

    open() {
        this.backdrop.hidden = false;
    }

    close() {
        this.backdrop.hidden = true;
        this.showMessage('');
    }
}

export class CategoryModal extends BaseModal {
    constructor({ title, onSubmit }) {
        super(title);
        this.onSubmit = onSubmit;
        this.saveButton = createElement('<button class="btn-primary" type="button">Сохранить</button>');
        this.cancelButton = createElement('<button class="btn-secondary" type="button">Отмена</button>');
        this.form = createElement(`
            <form class="stack">
                <input type="hidden" name="id" />
                <label>Название
                    <input type="text" name="title" required />
                </label>
                <label>Slug
                    <input type="text" name="slug" placeholder="optional" />
                </label>
                <label>Порядок
                    <input type="number" name="sort" value="0" />
                </label>
                <label class="flex" style="margin-top:6px;">
                    <input type="checkbox" name="is_active" checked /> Активна
                </label>
            </form>
        `);
        const actions = createElement('<div class="actions"></div>');
        actions.append(this.saveButton, this.cancelButton);
        this.modal.appendChild(this.form);
        this.modal.appendChild(actions);
        this.saveButton.addEventListener('click', () => this.submit());
        this.cancelButton.addEventListener('click', () => this.close());
    }

    setData(category) {
        this.form.querySelector('input[name="id"]').value = category?.id || '';
        this.form.querySelector('input[name="title"]').value = category?.title || '';
        this.form.querySelector('input[name="slug"]').value = category?.slug || '';
        this.form.querySelector('input[name="sort"]').value = category?.sort ?? 0;
        this.form.querySelector('input[name="is_active"]').checked = category?.is_active ?? true;
    }

    async submit() {
        if (this.saveButton.disabled) return;
        this.showMessage('');
        this.saveButton.disabled = true;
        try {
            await this.onSubmit({
                id: this.form.querySelector('input[name="id"]').value,
                title: this.form.querySelector('input[name="title"]').value.trim(),
                slug: this.form.querySelector('input[name="slug"]').value.trim(),
                sort: Number(this.form.querySelector('input[name="sort"]').value) || 0,
                is_active: this.form.querySelector('input[name="is_active"]').checked,
            });
            this.close();
        } catch (error) {
            this.showMessage(error.message, true);
        } finally {
            this.saveButton.disabled = false;
        }
    }
}

export class ItemModal extends BaseModal {
    constructor({ title, categoriesProvider, onSubmit }) {
        super(title);
        this.onSubmit = onSubmit;
        this.categoriesProvider = categoriesProvider;
        this.saveButton = createElement('<button class="btn-primary" type="button">Сохранить</button>');
        this.cancelButton = createElement('<button class="btn-secondary" type="button">Отмена</button>');
        this.form = createElement(`
            <form class="stack">
                <input type="hidden" name="id" />
                <label>Категория
                    <select name="category_id" required></select>
                </label>
                <label>Название
                    <input type="text" name="title" required />
                </label>
                <label>Slug
                    <input type="text" name="slug" placeholder="optional" />
                </label>
                <div class="form-row">
                    <label>Цена
                        <input type="number" name="price" step="0.01" value="0" />
                    </label>
                    <label>Порядок
                        <input type="number" name="sort" value="0" />
                    </label>
                </div>
                <label>Картинка (URL)
                    <input type="url" name="image_url" placeholder="https://..." />
                </label>
                <label>Короткий текст
                    <textarea name="short_text" placeholder="Краткое описание"></textarea>
                </label>
                <label>Описание
                    <textarea name="description" placeholder="Полное описание"></textarea>
                </label>
                <label class="flex" style="margin-top:6px;">
                    <input type="checkbox" name="is_active" checked /> Активен
                </label>
            </form>
        `);
        const actions = createElement('<div class="actions"></div>');
        actions.append(this.saveButton, this.cancelButton);
        this.modal.append(this.form, actions);
        this.saveButton.addEventListener('click', () => this.submit());
        this.cancelButton.addEventListener('click', () => this.close());
    }

    refreshCategories(type) {
        const select = this.form.querySelector('select[name="category_id"]');
        select.innerHTML = '';
        this.categoriesProvider(type).forEach((cat) => {
            const option = document.createElement('option');
            option.value = cat.id;
            option.textContent = cat.title;
            select.appendChild(option);
        });
    }

    setData(item, type) {
        this.refreshCategories(type);
        this.form.dataset.type = type;
        this.form.querySelector('input[name="id"]').value = item?.id || '';
        this.form.querySelector('select[name="category_id"]').value = item?.category_id || '';
        this.form.querySelector('input[name="title"]').value = item?.title || '';
        this.form.querySelector('input[name="slug"]').value = item?.slug || '';
        this.form.querySelector('input[name="price"]').value = item?.price ?? 0;
        this.form.querySelector('input[name="sort"]').value = item?.sort ?? 0;
        this.form.querySelector('input[name="image_url"]').value = item?.image_url || '';
        this.form.querySelector('textarea[name="short_text"]').value = item?.short_text || '';
        this.form.querySelector('textarea[name="description"]').value = item?.description || '';
        this.form.querySelector('input[name="is_active"]').checked = item?.is_active ?? true;
    }

    async submit() {
        if (this.saveButton.disabled) return;
        this.showMessage('');
        this.saveButton.disabled = true;
        try {
            const formType = this.form.dataset.type;
            await this.onSubmit({
                id: this.form.querySelector('input[name="id"]').value,
                type: formType,
                category_id: Number(this.form.querySelector('select[name="category_id"]').value),
                title: this.form.querySelector('input[name="title"]').value.trim(),
                slug: this.form.querySelector('input[name="slug"]').value.trim(),
                price: this.form.querySelector('input[name="price"]').value || 0,
                image_url: this.form.querySelector('input[name="image_url"]').value || null,
                short_text: this.form.querySelector('textarea[name="short_text"]').value || null,
                description: this.form.querySelector('textarea[name="description"]').value || null,
                is_active: this.form.querySelector('input[name="is_active"]').checked,
                sort: Number(this.form.querySelector('input[name="sort"]').value) || 0,
            });
            this.close();
        } catch (error) {
            this.showMessage(error.message, true);
        } finally {
            this.saveButton.disabled = false;
        }
    }
}
