import { register, login, logout, me } from './api.js';
const el = (id)=>document.getElementById(id);
const msg = el('auth-msg');
async function refresh(){
  try { const {user} = await me(); msg.textContent = `Вы вошли как ${user.email}`; el('btn-logout').style.display=''; }
  catch { msg.textContent = 'Вы не авторизованы.'; el('btn-logout').style.display='none'; }
}
el('btn-login').onclick = async ()=>{
  try{ await login(el('email').value.trim(), el('password').value);
       msg.textContent='Готово! Перехожу в каталог…'; setTimeout(()=>location.href='catalog.html',600);
  }catch(e){ msg.textContent='Ошибка входа: '+e.message; }
};
el('btn-signup').onclick = async ()=>{
  try{ await register(el('email').value.trim(), el('password').value, el('name').value.trim());
       msg.textContent='Регистрация успешна!'; setTimeout(()=>location.href='catalog.html',600);
  }catch(e){ msg.textContent='Ошибка регистрации: '+e.message; }
};
el('btn-logout').onclick = async ()=>{ await logout(); msg.textContent='Вы вышли.'; el('btn-logout').style.display='none'; };
refresh();
