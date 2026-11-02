Tüm modeller için çalışma talimatı:
1. Bir kod talep ettiğimde sadece anlaştığımız kodu yaz.
2. Test: yalnız bu işin RoadMap maddesinde adı geçen fixture/mocked testini çalıştır (`pytest` ilgili dosya, bir kez). Kırmızıysa sonucu göster; “geçir” demedikçe kovalama, suite’e test ekleme.
3. Terminal: mkdir, madde 2’deki dar pytest ve `docker compose config` dışında bir şey çalıştırma. Live Gemini, bilim API, `docker compose up`, Inspector, `pytest tests/` — hayır.
4. Tamamlanan işlerden sonra eğer test etmem gerekirse POSTMAN'e import etmem için curl ile import kodu yaz. WebSocket ise zarf örneği (`ask` / `cancel` / server event) yaz; REST yoksa cURL uydurma.
5. bir kod yazacağın zaman kod tekrarı yapmamaya özen göster. Mesela bir veritabanına ya da benzeri bir araca bağlanacaksın ya da query'ler göndereceksin. Eğer servisler katmanlar zaten yazıldıysa önce halihazırda yazılmış olan servis metodlarını bul, mümkünse bunları kullan.
6. Bu değişiklik için yazabileceğim commit mesajını da ekle.

Cevabını mümkün olduğunca şu sırayla ver:

- Değiştirilen / oluşturulan dosyalar ve Kod blokları
- Kod bloklarını verirken koddaki yerine linklenebilecek şekilde yaz.
- Doğrulama: agent’ın çalıştırdığı dar test vs benim çalıştırmam gereken live/demo komutları
- REST API varsa Postman için cURL örnekleri; WS varsa zarf örneği
