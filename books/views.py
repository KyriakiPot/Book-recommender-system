from neomodel import db
from django.shortcuts import render
from django.http import HttpResponse
from py2neo import Graph, Node, Relationship
import time
from .forms import SearchForm
import base64
import re
from django.core.paginator import Paginator
from collections import Counter

graph = Graph("bolt://localhost:11006")

#home page that shows books which have average rating above 4.2 and the highest number of ratings
def index(request):
    start_time = time.time()
    #delete user from session and log out
    if request.method == 'POST' and 'user_id' in request.session:
        value = request.POST.get('logout')
        del request.session['user_id']

    k=0
    best_book = []
    #return the best book from each genre
    best_book =graph.run("""MATCH (b:Books)-[:HAS_TAG]->(t:Tags) 
                            WHERE b.average_rating > 4.2 
                            RETURN b.title as title,b.ratings_count as count,b.image_url as image,b.average_rating as average,b.author as author, 
                            b.original_publication_year as year,b.bookId as id,collect(DISTINCT t.tagName) as tag ORDER BY average DESC LIMIT 30 """).data()
    my_dict = {'insert_me': best_book}
    print("--- %s seconds home page ---" % (time.time() - start_time))
    
    return render(request,'books/index.html',context=my_dict)

#page that shows a book information and 8 similar books
def book_info(request):
    start_time = time.time()
    book_info = []
    similar_book = []

    if request.method == 'POST':
        #get book title
        title = request.POST.get('title')
        #retrieve book information
        book_info = graph.run("""
                                MATCH (b:Books {title: $t})-[:HAS_TAG]->(t:Tags) 
                                RETURN b.title as title,b.ratings_count as count,b.image_url as image,b.average_rating as average,b.author as author, 
                                b.original_publication_year as year,b.bookId as id,collect(DISTINCT t.tagName) as tag,b.language as language LIMIT 1""",t=title).data()
        request.session['book'] = book_info

        if 'user_id' in request.session.keys():
            #if a user logs in, item-based collaboration filtering will be used
            id = request.session['user_id'] 
            user_rates = graph.run("MATCH (u:Users {userName:$u})-[r:Rates]->(b:Books) RETURN b.title as title",u = id).data()
            user_rates = [d['title'] for d in user_rates]  
            similar_book = calc_ratings2(id,title,user_rates,8)
        else:
            #else similar books are those where have high similarity,belong to the same genre and the distance of average rating is smaller or equal to 1
            id = None
            similar_book = graph.run("""
                                        MATCH (t1:Tags)<-[h1:HAS_TAG]-(b1:Books {title:$t})-[r:Has_Similarity]->(b2:Books)-[h2]->(t1) 
                                        WHERE abs(b1.average_rating-b2.average_rating)<=1 
                                        RETURN r.similarity as similarity,b2.title as title,b2.image_url as image ORDER BY similarity DESC LIMIT 8""",t=title).data()

        request.session['similar_book'] = similar_book
        print("--- %s seconds --- book info" % (time.time() - start_time))
        return render(request,'books/book_info.html',context={'book' : book_info,'id' : id, 'similar_book' : similar_book})
    else:
        print("--- %s seconds --- book info" % (time.time() - start_time))
        return render(request,'books/book_info.html',context={'book' : request.session['book'], 'similar_book' : request.session['similar_book']})

#page that shows books with specific genre
def genres(request):
    books = []
    genre = ""
    start_time = time.time()
    if request.method == 'POST':
        #this case refers to a logged in user that POST a request
        if 'user_id' in request.session.keys():
            genre = request.POST.get('item') 
            request.session['genre'] = genre
            id = request.session['user_id']       
            books = graph.run("""MATCH (b:Books)-[r:HAS_TAG]->(t:Tags) WITH collect(DISTINCT t.tagName) as tag, b.title as title,b.image_url as image,
                                 b.author as author,b.original_publication_year as year,b.average_rating as rating,b  
                                 WHERE $g in tag and  b.average_rating is not null and b.ratings_count is not null RETURN tag, title, image, author, year,rating 
                                 ORDER BY rating DESC""",g=genre).data()
            context = {
                'genre' : books,
                'id' : id,
                'category' : genre
                }
            print("--- %s seconds --- genre" % (time.time() - start_time))
            return render(request, 'books/genres.html', context = context)
        #this case refers to a user without log in that POST a request
        else:
            genre = request.POST.get('item') 
            request.session['genre'] = genre
            books = graph.run("""MATCH (b:Books)-[r:HAS_TAG]->(t:Tags) WITH collect(DISTINCT t.tagName) as tag, b.title as title,b.image_url as image,
                                 b.author as author,b.original_publication_year as year,b.average_rating as rating,b  
                                 WHERE $g in tag and  b.average_rating is not null and b.ratings_count is not null RETURN tag, title, image, author, year,rating  
                                 ORDER BY rating DESC""",g=genre).data()
            print("--- %s seconds --- genre" % (time.time() - start_time))
            return render(request, 'books/genres.html', {'genre' : books, 'category' : genre})        
    
    #this case refers to a logged in user that rates a book from that page 
    if 'user_id' in request.session.keys():
        id = request.session['user_id']   
        genre = request.session['genre'] 
        books = graph.run("""MATCH (b:Books)-[r:HAS_TAG]->(t:Tags) WITH collect(DISTINCT t.tagName) as tag, b.title as title,b.image_url as image,b.author as author,
                             b.original_publication_year as year,b.average_rating as rating,b  
                             WHERE $g in tag and  b.average_rating is not null and b.ratings_count is not null 
                             RETURN tag, title, image, author, year,rating  ORDER BY rating DESC""",g=genre).data()
        context = {
            'genre' : books,
            'id' : id,
            'category' : genre
            }
        if request.method == 'GET':
            rating = request.GET.get('rating')
            if rating != None:
                rating,title = rating.split(",")
                rate = graph.run("""MATCH (u:Users),(b:Books) 
                                    WHERE u.userName = $u AND b.title = $t MERGE (u)-[r:Rates]->(b) SET r.rating = $r RETURN r""",u=id,t=title,r=rating).data()
            print("--- %s seconds --- genre" % (time.time() - start_time))
            return render(request, 'books/genres.html', context = context)    

    else:
            genre = request.session['genre']
            books = graph.run("""MATCH (b:Books)-[r:HAS_TAG]->(t:Tags) WITH collect(DISTINCT t.tagName) as tag, b.title as title,b.image_url as image,
                                 b.author as author,b.original_publication_year as year,b.average_rating as rating,b  
                                 WHERE $g in tag and  b.average_rating is not null and b.ratings_count is not null RETURN tag, title, image, author, year,rating  
                                 ORDER BY rating DESC""",g=genre).data()
            print("--- %s seconds --- genre" % (time.time() - start_time))
            return render(request, 'books/genres.html', {'genre' : books,'category' : genre}) 
                
#this page shows the result of both the advanced search and search by title
def result(request):
    start_time = time.time()
    genres = []
    result = []
    user_rates = []
    score = []
    i = 0

    if 'user_id' in request.session.keys():
        id = request.session['user_id'] 
    else:
        id = None
    
    if request.method == 'POST':
        #get user's input
        title = request.POST.get('title')
        genres = request.POST.getlist('genre')
        author =  request.POST.get('author_search')
        year =  request.POST.get('year_search')
        isbn =  request.POST.get('isbn_search')
        rating =  request.POST.get('rating_search')

        #search by title
        if title != None:
            result = graph.run("""MATCH (b:Books)-[:HAS_TAG]->(t:Tags) WHERE toLower(b.title) CONTAINS toLower($t) 
                                  RETURN b.title as title,b.author as author,b.original_publication_year as year,b.isbn as isbn,collect(DISTINCT t.tagName) as tag,
                                  b.image_url as image,b.average_rating as rating""",t=title).data()
            request.session['result'] = result
            request.session['page'] = 1
            p = Paginator(request.session['result'], 5)

        #search by other key such as author
        elif len(genres)>0 or author!=None or year!=None or isbn!=None or rating!=None:
            query = """MATCH (b:Books)-[:HAS_TAG]->(t:Tags) WITH b.average_rating as rating,b.title as title,b.author as author,
                       b.original_publication_year as year,b.image_url as image,collect(DISTINCT t.tagName) as tag,b.isbn as isbn WHERE """             
            #make the where clause
            if len(genres) > 0:
                query = query + 'and [n IN $t WHERE  n IN tag] '
                i = 1

            if author != '':
                query = query + 'and toLower(author) CONTAINS toLower($a) '
                i = 1

            if year != '':
                query = query + 'and year>=$y '
                i = 1

            if isbn != '':
                query = query + 'and b.isbn = $i '
                i = 1

            if rating != None:
                query = query + 'and rating > toFloat($r) ' 
                i = 1

            query = query.replace('and', '', 1)
            query = query + "RETURN title,image,rating,author,year,tag,isbn ORDER BY rating DESC"

            if i==1:
                result = graph.run(query,a=author,y=year,r=rating,t=genres,i=isbn).data() 
            
            request.session['result'] = result
            request.session['page'] = 1
            #split the results so that each time only 5 books will be shown 
            p = Paginator(request.session['result'], 5)
        #move into the next page
        else:
            p = Paginator(request.session['result'], 5)
            if p.num_pages > request.session['page']:
                request.session['page'] = request.session['page'] + 1
            else:
                #delete sessions when all the results were shown
                del request.session['page']
                del request.session['result']
                del request.session['myresult']
                request.session['myresult'] = ['These are all the results']
                print("--- %s seconds --- result" % (time.time() - start_time))
                return render(request,'books/result.html',{'new_form' : request.session['myresult'] , 'id' : id})
        
        #a case which the user doesn't give a valid input
        if 'myresult' not in request.session.keys():
            request.session['myresult'] = ['Not valid input! Please enter a valid value!']
            print("--- %s seconds --- result" % (time.time() - start_time))
            return render(request,'books/result.html',{'new_form' : request.session['myresult'], 'id' : id})
       
        #retrieve similar books based on logged in user
        if 'user_id' in request.session.keys():
            myresult = p.page(request.session['page']).object_list  
            user_rates = graph.run("MATCH (u:Users {userName:$u})-[r:Rates]->(b:Books) RETURN b.title as title",u = id).data()
            user_rates = [d['title'] for d in user_rates]  
            for i in range(len(myresult)):
                rtitle = myresult[i]['title']
                #calculate item-based collaboration filtering
                myresult[i]["similarbook"] = calc_ratings2(request.session['user_id'],rtitle,user_rates,2)
        #retrieve similar books based on user's not logging in
        else: 
            myresult = p.page(request.session['page']).object_list   
            for i in range(len(myresult)):
                rtitle = myresult[i]['title']
                #retrieve books with high similarity,same genre and distance smaller or equal to 1
                myresult[i]["similarbook"] = graph.run("""MATCH (t1:Tags)<-[h1:HAS_TAG]-(b1:Books {title:$t})-[r:Has_Similarity]->(b2:Books)-[h2]->(t1) 
                                                          WHERE abs(b1.average_rating-b2.average_rating)<=1  
                                                          RETURN r.similarity as similarity,b2.title as title,b2.image_url as image 
                                                          ORDER BY r.Similarity DESC LIMIT 2""",t=rtitle).data()
        
        print("--- %s seconds --- result" % (time.time() - start_time))
        request.session['myresult'] = myresult      
        return render(request,'books/result.html',{'new_form' : myresult, 'id' : id})
    else:
        print("--- %s seconds --- result" % (time.time() - start_time))
        return render(request,'books/result.html',{'new_form' : request.session['myresult'], 'id' : id})
        
    
#sign up page that shows books for rating 
def signup(request):
    start_time = time.time()
    best_books = []

    best_books = books() 
    print("--- %s seconds --- sign up" % (time.time() - start_time))        
    return render(request,'books/signup.html',{'books':best_books})

#retrive the best book from each category
def books():
    start_time = time.time()
    categories = []
    books = []
    best_books = []

    categories = graph.run("MATCH (t:Tags) RETURN t.tagName as tag ").data()
    for i in range(len(categories)):
        j=0
        books = graph.run("""MATCH (b:Books)-[r:HAS_TAG]->(t:Tags) WHERE t.tagName= $c and b.average_rating>4 
                             RETURN b.title as title,b.average_rating as rating,b.image_url as image 
                             ORDER BY b.ratings_count DESC LIMIT 10""",c=categories[i]['tag']).data()
        #reassure that a book will be shown only once
        if books[j] not in best_books:
            best_books.append(books[j])
        else:
            while books[j] in best_books:
                j = j+1
            best_books.append(books[j])          
    for i in range(len(categories)):
        best_books[i]["tag"] = categories[i]["tag"]
    print("--- %s seconds --- best books" % (time.time() - start_time)) 
    return best_books

#user's sign up
def success(request):
    start_time = time.time()

    characters = ('[A-Z]', '[a-z]', '[0-9]')
    #get user's input and check if username exists, 
    #if password has length more than six, 
    #if password has both letters and numbers and if both of the passwords match
    if request.method == 'POST':
        name = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        user = graph.run("Match (u:Users) Where u.userName = $u Return u.userName",u=name).data()
        if len(user) != 0:
            print("--- %s seconds --- log in" % (time.time() - start_time))  
            return render(request,'books/success.html',{'message': 'The username already exists, try another one!'})

        elif password != password2:
            print("--- %s seconds --- log in" % (time.time() - start_time))  
            return render(request,'books/success.html',{'message': 'The passwords are different,try again'})

        elif len(password) >= 6 and not(password.isalpha() or password.isnumeric()): 
            #encode password
            password = password.encode("utf-8")
            encoded = str(base64.b64encode(password))
            new = graph.run("CREATE (u:Users) SET u.userName=$u, u.password=$p RETURN u ",u=name,p=encoded).data()
            categories = graph.run("MATCH (t:Tags) WHERE t.tagName<>'none' RETURN t.tagName as tag ").data()

            #store user's ratings
            for i in range(len(categories)):
                data = "rating" + categories[i]["tag"] 
                rating = request.POST.get(data)
                if rating != None:
                    rate = graph.run("""MATCH (u:Users),(b:Books) WHERE u.userName = $u AND b.title = $t CREATE (u)-[r:Rates]->(b) SET r.rating = $r 
                                        RETURN r""",u=name,t=books()[i]['title'],r=rating).data()
            print("--- %s seconds --- log in" % (time.time() - start_time))    
            return render(request,'books/success.html',{'message': 'You sign up successfully'})
        else:
            print("--- %s seconds --- log in" % (time.time() - start_time))   
            return render(request,'books/success.html',{'message': 'Your password should be at least 6 characters and contain both letters and numbers'})
    print("--- %s seconds --- log in" % (time.time() - start_time))  
    return render(request,'books/success.html',{})

#home page of logged in user 
def user_index(request):
    start_time = time.time()
    user_rates = []
    if request.method == 'POST':
        name = request.POST.get('username')
        password = request.POST.get('password')
        password = password.encode("utf-8")
        encoded = str(base64.b64encode(password))
        
        user = graph.run("MATCH (u:Users) WHERE u.userName= $u and u.password= $p RETURN u.userId as id,u.userName as name",u=name,p=encoded).data()
        
        #validate user
        if(len(user)>0):
            id = user[0]['name']
            request.session['user_id'] = id
            user_rates = graph.run("""MATCH (u:Users {userName:$u})-[r:Rates]->(b:Books)-[:HAS_TAG]->(t) 
                                      WITH collect(t.tagName) as tag,b,r RETURN b.bookId,r.rating as rating,b.title as title,tag,b.author as author,
                                      b.original_publication_year as year,b.isbn as isbn,b.image_url as image""",u = request.session['user_id']).data()
            #predict based on user-based collaboration filtering
            prediction = calc_ratings(id,user_rates)
            
            #show top 30 list of books
            popular = books() 
                
            print("--- %s seconds --- user's home page" % (time.time() - start_time)) 
            return render(request,'books/user_index.html',{'message': prediction, 'popular' : popular, 'id' : id,'rate' : user_rates})
        else:   
            print("--- %s seconds --- user's home page" % (time.time() - start_time))     
            return render(request,'books/success.html',{'message':"Invalid input! The username or password is wrong. Please try again!"})

    #a case which user rates a book
    if 'user_id' in request.session.keys():
        id = request.session['user_id']
        user_rates = graph.run("""MATCH (u:Users {userName:$u})-[r:Rates]->(b:Books)-[:HAS_TAG]->(t) WITH collect(t.tagName) as tag,b,r 
                                  RETURN b.bookId,r.rating as rating,b.title as title,tag,b.author as author,b.original_publication_year as year,b.isbn as isbn,
                                  b.image_url as image""",u = request.session['user_id']).data()
        prediction = calc_ratings(id,user_rates) 

        popular = books()
        if request.method == 'GET':
            rating = request.GET.get('rating')
            if rating != None:
                rating,title = rating.split(",")
                rate = graph.run("""MATCH (u:Users),(b:Books) WHERE u.userName = $u AND b.title = $t MERGE (u)-[r:Rates]->(b) SET r.rating = $r 
                                    RETURN r""",u=id,t=title,r=rating).data()
  
        print("--- %s seconds --- user's home page" % (time.time() - start_time)) 
        return render(request,'books/user_index.html',{'message': prediction, 'popular' : popular, 'id' : id,'rate' : user_rates})

    return render(request,'books/user_index.html',{'message' : 'Please log in!'})

#user-based collaborative filtering
def calc_ratings(id,user_rates):
    start_time = time.time()
    nearest_neighbors = 10
    overlap = []
    nn_ratings = []
    nn_prediction = []
    final = []
    info = {}
    bookId = []
    user_rates = [d['b.bookId'] for d in user_rates]
    
    #calculate overlap similarity
    overlap = graph.run(""" MATCH (u1:Users {userName: $u})-[:Rates]->(books1) WITH u1, collect(books1.bookId) AS b1Books
                            MATCH (u2:Users )-[:Rates]->(books2) WITH u1, b1Books, u2, collect(books2.bookId) AS b2Books
                            WHERE u1<>u2 WITH gds.alpha.similarity.overlap(b1Books, b2Books) AS s,u2
                            ORDER BY s DESC LIMIT $nn RETURN collect(u2.userName) AS id,collect(s) as similarity """,u=id,nn=nearest_neighbors).data()

    #return nearest neighbors' ratings
    nn_ratings = graph.run("""  MATCH (u:Users)-[r:Rates]->(b:Books)-[:HAS_TAG]->(t:Tags)  WHERE u.userName IN $NN and r.rating IS NOT NULL and not b.bookId in $b 
                                RETURN u.userName as uid,b.bookId as bid, b.title as title,b.ratings_count as count,b.image_url as image,
                                r.rating as rating,b.author as author, b.original_publication_year as year,collect(DISTINCT t.tagName) as tag,
                                b.average_rating as average ORDER BY bid""", NN = overlap[0]['id'],b=user_rates).data()

    #calculate possible rating by the above formula
    #rating = (sum(rating*similarity) / sum(similarity)
    if len(overlap[0]['id']) > 0:
        s = 0
        weight = 0
        similarity = 0 
        sum = []
        for i in range(len(nn_ratings)):
            for j in range(nearest_neighbors):
                if nn_ratings[i]["uid"] == overlap[0]['id'][j]:
                    weight = float(nn_ratings[i]["rating"]) * float(overlap[0]['similarity'][j])
                    similar = overlap[0]['similarity'][j]
            if i !=0 and nn_ratings[i]["bid"] != nn_ratings[i-1]["bid"] or i == len(nn_ratings)-1:
                s = s/similarity	
                if s >= 3:
                    sum.append([s, nn_ratings[i-1]["bid"],nn_ratings[i-1]["title"],nn_ratings[i-1]["author"],nn_ratings[i-1]["year"],nn_ratings[i-1]["image"],nn_ratings[i-1]["tag"],nn_ratings[i-1]["average"]])
                s=weight
                similarity = similar
            else:
                s = s + weight
                similarity = similarity + similar
        for i in range (len(sum)):
            info = {
                #calculate final rating by multiplying score with the average book's rating
                'cf_rating' : sum[i][0],
                'title' : sum[i][2],
                'author' : sum[i][3],
                'year' : sum[i][4],
                'image' : sum[i][5],
                'tag' : sum[i][6],
                'rating' : sum[i][7]
            }
            final.append(info)

        #remove duplicates
        myfinal = [] 
        k = [x['title'] for x in final]
        for i in Counter(k):
            all = [x for x in final if x['title']==i]
            myfinal.append(max(all, key=lambda x: x['title']))

        print("--- %s seconds --- user-based" % (time.time() - start_time)) 
        return (myfinal)
    else:
        print("--- %s seconds --- user-based" % (time.time() - start_time)) 
        return (myfinal)

#item-based collaboration filtering
def calc_ratings2(id,rtitle,user_rates,mylimit):
    start_time = time.time()
    prediction = []
    similarity = []
    similar_books = []
    nearest_neighbor = []
    myresult = []
    limit = 10
    sum_similarity = 0
    sum_rating = 0
    result = []
    #retrieve 10 nearest neighbors based on cosine similarity
    similarity = graph.run("""MATCH (b1:Books {title:$t})-[h:Has_Similarity]->(b2:Books) 
                              RETURN h.similarity as similarity,b2.title as title ORDER BY similarity DESC LIMIT $l""",t=rtitle,l=limit)
    similar_books = [d['title'] for d in similarity]   
    #calculate score using weighted average
    for i in range(len(similar_books)):
        for j in range(len(user_rates)):
            if similar_books[i] != user_rates[j]:
                #for each similar book, retrieve user rating and similarity between books that the user rates and the similar book
                nearest_neighbor = graph.run("""MATCH (u:Users {userName:$u})-[r:Rates]->(b1:Books {title: $b1})-[h:Has_Similarity]->(b2:Books {title: $b2}) 
                                                RETURN r.rating as rating,h.similarity as similarity""",u=id,b1=user_rates[j],b2=similar_books[i]).data()
                if len(nearest_neighbor)>0:
                    sum_rating = sum_rating + (nearest_neighbor[0]['similarity'] * float(nearest_neighbor[0]['rating']))
                    sum_similarity = sum_similarity + nearest_neighbor[0]['similarity']
        if sum_similarity != 0:
            score = sum_rating / sum_similarity
            if score >=3:
                prediction.append({
                                    'score' : score,
                                    'book' : similar_books[i]
                                })  
            sum_similarity = 0
            sum_rating = 0
            
    prediction = sorted(prediction, key = lambda i: i['score'])

    if mylimit < len(prediction):
        for i in range(mylimit):
            myresult.append(graph.run("MATCH (b1:Books {title:$t}) RETURN b1.title as title,b1.image_url as image",t=prediction[i]['book']).data()) 
            result.append(myresult[i][0]) 
    else:
        for i in range(len(prediction)):
            myresult.append(graph.run("MATCH (b1:Books {title:$t}) RETURN b1.title as title,b1.image_url as image",t=prediction[i]['book']).data()) 
            result.append(myresult[i][0]) 


    print("--- %s seconds --- item-based" % (time.time() - start_time)) 
    return(result)



    
