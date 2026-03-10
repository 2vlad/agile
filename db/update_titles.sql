-- Update document titles to human-readable Russian names with authors

-- Статьи Ильи Павличенко (agile-organizations.ru)
UPDATE documents SET title = 'Рабочие соглашения — И. Павличенко' WHERE filename = '01_rabochie_soglasheniya.txt';
UPDATE documents SET title = 'Тренинг «Дизайн Agile-организаций» + Карта гипотез — И. Павличенко' WHERE filename = '01_scrum_ru_cod.txt';
UPDATE documents SET title = 'Дизайн Agile-организаций: обзор подхода — И. Павличенко' WHERE filename = '02_agile_organizations_ru_main.txt';
UPDATE documents SET title = 'Награды как инструмент оргдизайна — И. Павличенко' WHERE filename = '02_nagrady_kak_instrument_orgdizaina.txt';
UPDATE documents SET title = 'Традиционные и Agile-организации — И. Павличенко' WHERE filename = '03_agile_organizations_blog_traditsionnie.txt';
UPDATE documents SET title = 'Стратегический фокус и Карта гипотез — И. Павличенко' WHERE filename = '03_strategicheskii_fokus_karta_gipotez.txt';
UPDATE documents SET title = 'Когда Agile — это локальная оптимизация — И. Павличенко' WHERE filename = '04_kogda_agile_lokalnaya_optimizatsiya.txt';
UPDATE documents SET title = 'Три типа продуктовых групп — И. Павличенко' WHERE filename = '05_tri_tipa_produktovyh_grupp.txt';
UPDATE documents SET title = 'Насколько согласован ваш бизнес-портфель? — И. Павличенко' WHERE filename = '06_soglasovan_biznes_portfel.txt';
UPDATE documents SET title = 'Продвинутая Heat Map: частота и специфичность — И. Павличенко' WHERE filename = '07_prodvinutaya_heat_map.txt';
UPDATE documents SET title = 'Три метрики адаптивности: LeSS vs SAFe — И. Павличенко' WHERE filename = '08_tri_metriki_adaptivnosti_less_safe.txt';
UPDATE documents SET title = 'Кейс проектирования продуктовой группы — И. Павличенко' WHERE filename = '09_keis_proektirovaniya_produktovoi_gruppy.txt';
UPDATE documents SET title = 'Подходит ли базовая структура вашей компании? — И. Павличенко' WHERE filename = '10_podhodit_li_bazovaya_struktura.txt';
UPDATE documents SET title = 'Конфликты стратегических фокусов — И. Павличенко' WHERE filename = '11_konflikty_strategicheskih_fokusov.txt';
UPDATE documents SET title = 'Четыре перспективы структурирования продуктовых групп — И. Павличенко' WHERE filename = '12_chetyre_perspektivy_strukturirovaniya.txt';
UPDATE documents SET title = 'Почему LeSS нельзя скрестить с SAFe — И. Павличенко' WHERE filename = '13_less_nelzya_skrestit_s_safe.txt';
UPDATE documents SET title = '«Да, у нас продукт» — И. Павличенко' WHERE filename = '14_da_u_nas_produkt.txt';
UPDATE documents SET title = 'Принципы успешных изменений — И. Павличенко' WHERE filename = '15_printsipy_uspeshnyh_izmenenii.txt';
UPDATE documents SET title = 'Иерархия стратегических фокусов — И. Павличенко' WHERE filename = '16_ierarhiya_strategicheskih_fokusov.txt';
UPDATE documents SET title = 'Традиционные и Agile-организации — И. Павличенко' WHERE filename = '17_traditsionnie_i_agile_organizatsii.txt';
UPDATE documents SET title = 'Продуктовые группы в разных стратегических фокусах — И. Павличенко' WHERE filename = '18_produktovye_gruppy_v_raznyh_fokusah.txt';
UPDATE documents SET title = 'Воркшоп: стратегический фокус для банка — И. Павличенко' WHERE filename = '19_vorkshop_strategicheskii_fokus_bank.txt';
UPDATE documents SET title = 'Скорость против влияния — И. Павличенко' WHERE filename = '20_skorost_protiv_vliyaniya.txt';
UPDATE documents SET title = 'Семь шагов к эффективному мозговому штурму — И. Павличенко' WHERE filename = '21_sem_shagov_mozgovoi_shturm.txt';
UPDATE documents SET title = 'Продуктовые и прокси-метрики — И. Павличенко' WHERE filename = '22_produktovye_i_proksi_metriki.txt';
UPDATE documents SET title = 'Продукты и области ценности — И. Павличенко' WHERE filename = '23_produkty_i_oblasti_tsennosti.txt';
UPDATE documents SET title = 'От матрицы к простоте: кейс FMC Subsea — И. Павличенко' WHERE filename = '24_fmc_subsea_ot_matritsy_k_prostote.txt';
UPDATE documents SET title = 'Что оптимизируют ваши Agile-команды? — И. Павличенко' WHERE filename = '25_chto_optimiziruyut_agile_komandy.txt';
UPDATE documents SET title = 'Дизайн Agile-организаций: основные принципы — И. Павличенко' WHERE filename = '26_dizain_agile_organizatsii_osnovnie_printsipy.txt';

-- Внешние статьи (LeSS, Management 3.0, Corporate Rebels, Valve)
UPDATE documents SET title = 'Роль менеджера в LeSS — Б. Водде, К. Ларман' WHERE filename = '05_less_role_of_manager.txt';
UPDATE documents SET title = 'Самоуправляемые команды в LeSS — Б. Водде, К. Ларман' WHERE filename = '06_less_self_managing_teams.txt';
UPDATE documents SET title = 'ВкусВилл: революция в российском ритейле — Corporate Rebels' WHERE filename = '07_vkusvill_corporate_rebels.txt';
UPDATE documents SET title = 'Руководство для новых сотрудников Valve — Valve (2012)' WHERE filename = '08_valve_handbook_ru.txt';
UPDATE documents SET title = 'Management 3.0: введение — Ю. Аппело' WHERE filename = '04_management30_learn.txt';
UPDATE documents SET title = 'Роль коммодити-платформ в Agile — Ч. Рамос' WHERE filename = '09_commodity_platforms_cao.txt';

-- Книги
UPDATE documents SET title = 'Creating Agile Organizations — И. Павличенко, Ч. Рамос' WHERE filename LIKE 'Creating_Agile%';
UPDATE documents SET title = 'Выпускники вузов РФ: ИТ и Digital — исследование' WHERE filename LIKE 'Выпускники%';
UPDATE documents SET title = 'Дизайн Аджайл-организаций: конспект — И. Павличенко' WHERE filename LIKE 'Дизаин%';
UPDATE documents SET title = 'Agile-менеджмент: лидерство и управление командами — Ю. Аппело' WHERE filename LIKE 'Менеджмент%';
UPDATE documents SET title = 'Пятая дисциплина — П. Сенге' WHERE filename LIKE 'Пятая%';
